from IMDbScraper import IMDbScraper
from selenium import webdriver
import json

driver = webdriver.Chrome()
scraper = IMDbScraper(driver=driver, verbose=True,)

# top_250_movie_dict = scraper.scrape_top_250(save=True)
# all_movie_list_dict = scraper.crape_all_movies_list(save=True)

top_250_movies = json.load(open('json_files/top_250_movies.json'))
all_movies = json.load(open('json_files/all_movies_list.json'))

scraper.export_movie_list_to_csv(top_250_movies, './csv_files/top_250_movies.csv')
scraper.export_movie_list_to_csv(all_movies, './csv_files/all_movies_list.csv')

scraper.save_all_jsons_to_csv()
