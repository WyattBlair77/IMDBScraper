import lxml.html
from lxml import etree
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import time
import json
import pandas as pd
import os


class IMDbScraper():
    def __init__(self, driver, verbose=False):
        self.driver = driver
        self.verbose = verbose
        self.movie_lists = []

    def scrape_individual_movie_page(self, page_source):

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


    def scrape_top_250(self, save=True):
        top_250_url = 'https://www.imdb.com/chart/top/'
        self.driver.get(top_250_url)

        table_xpath = '//*[@id="main"]/div/span/div/div/div[3]/table/tbody'

        page_source_titles = self.driver.page_source
        root = lxml.html.fromstring(page_source_titles)
        titles = root.xpath(table_xpath + '//tr/td[2]/a//text()')

        movie_list = []
        for count, title in enumerate(titles):
            # Reload the top 250 page
            self.driver.get(top_250_url)

            # Click movie
            title_link = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.LINK_TEXT, title)))
            title_link.click()

            # Add to movie_dict dictionary
            individual_page_source = self.driver.page_source
            movie_page = self.scrape_individual_movie_page(individual_page_source)
            movie_page['Title'] = title
            movie_page = dict(reversed(list(movie_page.items())))
            movie_list.append(movie_page)

            if self.verbose:
                print(title, '(', count+1, '/', len(titles), '):')
                print(movie_list[count])

        if save:
            self.try_remove_file('./json_files/top_250_movies.json')
            with open('./json_files/top_250_movies.json', 'w') as fp:
                json.dump(movie_list, fp)

        return movie_list
    # movie_dict is formatted like this:
    # {'Movie Name':{'Director(s)': list, 'Genres': list, 'Stars': list, 'Runtime': string, 'Profit': int, ...
    # 'Release_Date': string (DAY MONTH YEAR), 'IMDB_Rating': float, 'Popularity': int}


    def scrape_all_movies_list(self, save=True):
        list_url = 'https://www.imdb.com/list/ls005750764/?st_dt=&mode=simple&page=1&ref_=ttls_vw_smp&sort=list_order,asc'
        self.driver.get(list_url)

        movie_list = []
        num_pages = 16
        for page in range(num_pages):
            if self.erbose:
                print('****'*3,'Looking at page : ', page+1, '****'*3)

            current_list_url = list_url.replace('page=1', 'page=' + (str(page + 1)))
            self.driver.get(current_list_url)

            table_xpath = '//*[@id="main"]/div/div[3]/div[3]'
            page_source = self.driver.page_source
            titles = self.scrape_titles_from_list(page_source, table_xpath)

            for count, title in enumerate(titles):
                # Reload the top 250 page
                self.driver.get(current_list_url)

                # Click movie
                title_link = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.LINK_TEXT, title)))
                title_link.click()

                # Add to movie_dict dictionary
                individual_page_source = self.driver.page_source
                movie_page = self.scrape_individual_movie_page(individual_page_source)
                movie_page['Title'] = title
                movie_page = dict(reversed(list(movie_page.items())))
                movie_list.append(movie_page)

                if self.verbose:
                    print(title, '(', count + 1, '/', len(titles), '):')
                    print(movie_list[-1])

            # driver.get(current_list_url)
            # click_next_link(page_source, driver, verbose)

        if save:
            self.try_remove_file('./json_files/all_movies.json')
            with open('./json_files/all_movies.json', 'w') as fp:
                json.dump(movie_list, fp)

        return movie_list


    def click_next_link(self, page_source):
        root = lxml.html.fromstring(page_source)
        tree = etree.ElementTree(root)
        next_link_xpath = ''

        footer = root.xpath('/html/body/div[3]/div/div[2]/div[3]/div[1]/div/div[3]/div[5]')[0]
        for child in footer.iter():
            if child.tag == 'a' and child.get('class') == 'flat-button lister-page-next next-page':
                next_link_xpath = tree.getpath(child)

        next_link = WebDriverWait(self.driver, 5).until(
            EC.presence_of_element_located((By.XPATH, next_link_xpath)))
        next_link.click()

        if self.verbose:
            print('Clicked next')

        time.sleep(5)


    def scrape_titles_from_list(self, page_source_titles, table_xpath):
        root = lxml.html.fromstring(page_source_titles)
        table = root.xpath(table_xpath)[0]

        titles = []
        for child in table.iter():
            if child.tag == 'a' and child.text is not None:
                titles.append(child.text)

        titles = list(filter(lambda x: not x.isspace() and '\n' not in x, titles))

        return titles


    def export_movie_list_to_csv(self, movie_list, filename='./csv_files/movies.csv', fill_empty_spots_with=None,):
        from itertools import chain
        all_sections = set(chain.from_iterable(movie_list))

        for d in movie_list:
            d.update((k, fill_empty_spots_with) for k in all_sections-d.keys())

        csv_dict = {}
        for col in movie_list[0].keys():
            csv_dict[col] = []

        for movie in movie_list:
            for col in movie.keys():
                csv_dict[col].append(movie[col])

        self.try_remove_file(filename)

        csv_frame = pd.DataFrame().from_dict(csv_dict, orient='columns')
        csv_frame.to_csv(filename)
        print('Saved movie_list to', filename)


    def try_remove_file(self, filename):
        try:
            os.remove(filename)
        except FileNotFoundError:
            print(filename + ' does not yet exist')


    def movie_lists_to_csv(self, list_of_movie_lists, filename='./csv_files/movies.csv'):
        movie_list = []
        for lst in list_of_movie_lists:
            for movie in lst:
                if movie not in movie_list:
                    movie_list.append(movie)

        self.export_movie_list_to_csv(movie_list, filename=filename)

    def save_all_jsons_to_csv(self, filename='./csv_files/every_saved_scrape.csv'):
        files = os.listdir('./json_files/')
        list_of_movie_lists = []

        for file in files:
            path = './json_files/' + file
            list_of_movie_lists.append(json.load(open(path)))

        self.movie_lists_to_csv(list_of_movie_lists, filename=filename)

    def set_movie_lists(self, movie_list):
        self.movie_lists = []



