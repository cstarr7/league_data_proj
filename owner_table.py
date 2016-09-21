# -*- coding: utf-8 -*-
"""
Created on Sun Feb 21 12:25:52 2016

@author: Charlie
"""

from lxml import html
import requests
import string
from selenium import webdriver
import sqlite3
from time import sleep


class Owner(object):
    #class to create object for any manager who has ever played in the league

    def __init__(self, name, league_start, league_end, league_ID):
       
        self.owner_name = name
        self.year_ID_pair = dict.fromkeys(range(league_start, league_end + 1), 0)
        self.league_ID = league_ID

    def __str__(self):

        return self.ownerName
    
    def set_year_ID(self, year, ID):
        # Each owner has a unique league ID which is not constant due to
        # additions and losses in membership
        
        self.year_ID_pair[year] = ID
    
    def get_ID(self, year):

        return self.yearIDpair[year]
    
    def add_draft_results(self, year, results):

        self.draft_results[year] = results
        return
    
    def get_draft_results(self, year):

        return self.draft_results[year]


class League(object):
    # League object will be a container for things associated with the
    # league (i.e owners, draft results, etc)

    def __init__(self, league_start, league_end, league_id, sql_db):

        self.league_start = league_start
        self.league_end = league_end
        self.league_id = league_id
        self.db = sql_db
        self.owners = self.populate_owners()
                
    def populate_owners(self):
        # Populate owners 
        #looks at each year of fantasy league and gets an owner ID for each season
        
        preamble = 'http://games.espn.go.com/ffl/leaguesetup/ownerinfo?leagueId='
        postID = '&seasonId='

        driver = webdriver.Firefox()
        owners = {}

        for year in range(self.league_start, self.league_end + 1):
            url = preamble + str(self.league_id) + postID + str(year)
            driver.get(url)
            if 'redir' in driver.current_url:
                sleep(20)
            element_tree = html.fromstring(driver.page_source)

            # unique identifier for each owner for given season is number
            # between 0 and 16 (use 20 to be safe)
            for element in element_tree.iter('span'):
                pre = 'ownerspan'
                post = '-0'
                for iter_owner in range(1,20):
                    owner_ID = pre + str(iter_owner) + post
                    #try because some owner IDs are not used and will fail
                    try:
                        name = element.get_element_by_id(owner_ID).text_content()
                        if name not in owners.keys():
                            owners[name] = Owner(
                                name, self.league_start, 
                                self.league_end, self.league_id
                                )
                        try:
                            owners[name].set_year_ID(year, iter_owner)
                        except:
                            continue                                            
                    except:
                        continue

        driver.close()
        return owners

    def create_owner_table(self):

        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute('''DROP TABLE IF EXISTS owners''')
        c.execute('''CREATE TABLE owners 
                    (real_id  INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
                    name  TEXT UNIQUE, 
                    id_2007 INTEGER, 
                    id_2008 INTEGER,
                    id_2009 INTEGER,
                    id_2010 INTEGER,
                    id_2011 INTEGER,
                    id_2012 INTEGER,
                    id_2013 INTEGER,
                    id_2014 INTEGER,
                    id_2015 INTEGER,
                    id_2016 INTEGER)''')

        for owner in self.owners.itervalues():
            payload = (owner.owner_name,) + tuple([owner.year_ID_pair[year] for year
                in range(self.league_start, self.league_end + 1)]
                )

            c.execute('''INSERT INTO owners (name, id_2007, id_2008, id_2009,
                id_2010, id_2011, id_2012, id_2013, id_2014, id_2015, id_2016) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', payload
                )

        conn.commit()
        conn.close()

def main(league_start, league_end, league_ID, sql_db):


    new_league = League(league_start, league_end, league_ID, sql_db)
    new_league.create_owner_table()


main(2007, 2016, 392872, 'sphs_friends.sqlite')       