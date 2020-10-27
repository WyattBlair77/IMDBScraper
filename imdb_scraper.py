import lxml.html
from lxml import etree
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import time
import json
import pandas as pd
import os


def scrape_individual_movie_page(page_source):

    root = lxml.html.fromstring(page_source)
    title_overview = root.xpath('//*[@id="title-overview-widget"]')[0]

    info = {}

    for child in title_overview.iter():

        # Director, Writers, Stars
        if child.tag == 'div' and child.get('class') == 'credit_summary_item':
            meta_info = []
            section = ''
            for grandchild in child.iter():
                if grandchild.tag == 'a':
                    meta_info.append(grandchild.text)
                if grandchild.tag == 'h4':
                    section = grandchild.text.replace(':', '')

            meta_info = list(filter(lambda x: 'more credit' not in x and '&' not in x, meta_info))
            if section == 'Directors':
                section = 'Director'
            elif section == 'Writers':
                section = 'Writer'
            info[section] = meta_info

        # Metascore
        if child.tag == 'div' and child.get('class') is not None and 'metacriticScore' in child.get('class'):
            for grandchild in child.iter():
                if grandchild.tag == 'span':
                    info['Metascore'] = int(grandchild.text)

        # Rating, Runtime, Genres, Release Date
        if child.tag == 'div' and child.get('class') == 'title_wrapper':
            for grandchild in child.iter():
                if grandchild.tag == 'div' and grandchild.get('class') == 'subtext':
                    info['Rating'] = grandchild.text.strip()
                    meta_info = []
                    for great_grandchild in grandchild.iter():
                        if great_grandchild.tag == 'a':
                            meta_info.append(great_grandchild.text.replace('(South', ''))
                    info['Genre(s)'] = meta_info[:-1]
                    info['Release Date'] = ' '.join(meta_info[-1].strip().split(' ')[:-1])

        # Popularity
        if child.tag == 'div' and child.get('class') == 'titleReviewBarSubItem':
            for grandchild in child.iter():
                if grandchild.tag == 'span' and grandchild.get('class') == 'subText':
                    pop_string = grandchild.text.replace('\n', '').replace('(', '').replace(',', '').strip()
                    if pop_string.isdecimal():
                        info['Popularity'] = int(pop_string)

        # IMDB Rating
        if child.tag == 'span' and child.get('itemprop') is not None and child.get('itemprop') == 'ratingValue':
            info['IMDB Rating'] = float(child.text)

    article = root.xpath('//*[@id="titleDetails"]')[0]

    # Gross Profit
    for child in article.iter():
        if child.tag == 'h4' and child.text is not None and 'Cumulative Worldwide Gross' in child.text:
            tree = root.getroottree()
            profit_xpath = tree.getpath(child.getparent()) + '//text()'
            profit = root.xpath(profit_xpath)
            if len(profit) > 0:
                profit = profit[-1].strip().replace('$', '').replace(',', '')
                if profit.isdecimal():
                    info['Profit'] = int(profit)
            else:
                info['Profit'] = 'None Reported'

    return info


def scrape_top_250(driver, verbose=False,):
    top_250_url = 'https://www.imdb.com/chart/top/'
    driver.get(top_250_url)

    table_xpath = '//*[@id="main"]/div/span/div/div/div[3]/table/tbody'

    page_source_titles = driver.page_source
    root = lxml.html.fromstring(page_source_titles)
    titles = root.xpath(table_xpath + '//tr/td[2]/a//text()')

    movie_list = []
    for count, title in enumerate(titles):
        # Reload the top 250 page
        driver.get(top_250_url)

        # Click movie
        title_link = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.LINK_TEXT, title)))
        title_link.click()

        # Add to movie_dict dictionary
        individual_page_source = driver.page_source
        movie_page = scrape_individual_movie_page(individual_page_source)
        movie_page['Title'] = title
        movie_page = dict(reversed(list(movie_page.items())))
        movie_list.append(movie_page)

        if verbose:
            print(title, '(', count+1, '/', len(titles), '):')
            print(movie_list[count])

    return movie_list
# movie_dict is formatted like this:
# {'Movie Name':{'Director(s)': list, 'Genres': list, 'Stars': list, 'Runtime': string, 'Profit': int, ...
# 'Release_Date': string (DAY MONTH YEAR), 'IMDB_Rating': float, 'Popularity': int}


def scrape_all_movies(driver, verbose=False):
    list_url = 'https://www.imdb.com/list/ls005750764/?sort=list_order,asc&st_dt=&mode=simple&page=1&ref_=ttls_vw_smp'
    driver.get(list_url)

    movie_list = []
    num_pages = 16
    for page in range(num_pages):
        if verbose:
            print('****'*3,'Looking at page : ', page+1, '****'*3)

        table_xpath = '//*[@id="main"]/div/div[3]/div[3]'
        page_source = driver.page_source
        titles = scrape_titles_from_list(page_source, table_xpath)
        current_list_url = driver.current_url

        for count, title in enumerate(titles):
            # Reload the top 250 page
            driver.get(current_list_url)

            # Click movie
            title_link = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.LINK_TEXT, title)))
            title_link.click()

            # Add to movie_dict dictionary
            individual_page_source = driver.page_source
            movie_page = scrape_individual_movie_page(individual_page_source)
            movie_page['Title'] = title
            movie_page = dict(reversed(list(movie_page.items())))
            movie_list.append(movie_page)

            if verbose:
                print(title, '(', count + 1, '/', len(titles), '):')
                print(movie_list[count])

        click_next_link(page_source, driver, verbose)

    return movie_list


def click_next_link(page_source, driver, verbose=False):
    root = lxml.html.fromstring(page_source)
    tree = etree.ElementTree(root)
    next_link_xpath = ''

    footer = root.xpath('/html/body/div[3]/div/div[2]/div[3]/div[1]/div/div[3]/div[5]')[0]
    for child in footer.iter():
        if child.tag == 'a' and child.get('class') == 'flat-button lister-page-next next-page':
            next_link_xpath = tree.getpath(child)

    print(next_link_xpath)
    next_link = WebDriverWait(driver, 5).until(
        EC.presence_of_element_located((By.XPATH, next_link_xpath)))
    next_link.click()

    if verbose:
        print('Clicked next')

    time.sleep(3)


def scrape_titles_from_list(page_source_titles, table_xpath):
    root = lxml.html.fromstring(page_source_titles)
    table = root.xpath(table_xpath)[0]

    titles = []
    for child in table.iter():
        if child.tag == 'a' and child.text is not None:
            titles.append(child.text)

    titles = list(filter(lambda x: not x.isspace() and '\n' not in x, titles))

    return titles


def export_movie_list_to_csv(movie_dict, fill_empty_spots_with=None):
    from itertools import chain
    all_sections = set(chain.from_iterable(movie_dict))

    for d in movie_dict:
        d.update((k, fill_empty_spots_with) for k in all_sections-d.keys())

    csv_dict = {}
    for col in movie_dict[0].keys():
        csv_dict[col] = []

    for movie in movie_dict:
        for col in movie.keys():
            csv_dict[col].append(movie[col])

    try_remove_file('movies.csv')

    csv_frame = pd.DataFrame().from_dict(csv_dict, orient='columns')
    csv_frame.to_csv('movies.csv')
    print('Saved movie_dict to ./movies.csv')


def try_remove_file(filename):
    try:
        os.remove(filename)
    except FileNotFoundError:
        print(filename + ' does not yet exist')


# driver = webdriver.Chrome()
# movie_dict = scrape_top_250(driver, verbose=True)

driver = webdriver.Chrome()
movie_dict = scrape_all_movies(driver, verbose=True)

# movie_dict = json.load(open('movie_dict.json'))
# try_remove_file('movie_dict.json')

with open('movie_dict_all.json', 'w') as fp:
    json.dump(movie_dict, fp)

export_movie_list_to_csv(movie_dict)
