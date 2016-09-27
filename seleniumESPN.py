from selenium import webdriver
from selenium.webdriver.common.keys import Keys
import time




class EspnPageLogin(object):
    #initialize webpage retrieval object 
    def __init__(self):
        self.driver = webdriver.Firefox()
    #get data from webpage
    def retrieve(self, url):
        #passing relevant url to Firefox
        self.driver.get(url)
        #check to see if redirected to login page
        #if so, enter credentials
        if 'redir' in self.driver.current_url:
            #time to manually enter user/pass
            time.sleep(20)
            '''userElement = self.driver.find_element_by_css_selector('#field-username-email > label:nth-child(1) > input:nth-child(2)')
            passElement = self.driver.find_element_by_css_selector('#field-password > label:nth-child(1) > input:nth-child(2)')
            userElement.send_keys(params['username'])
            passElement.send_keys(params['password'])
            passElement.submit()'''
        return self.driver.page_source
    #attempt to close browser, although this hasn't been working
    def teardown(self):
        self.driver.close()






