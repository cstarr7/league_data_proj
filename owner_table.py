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
import textwrap


class Owner(object):
    #class to create object for any manager who has ever played in the league

    def __init__(self, name, league_start, league_end, league_ID):
       
        self.owner_name = name
        self.year_ID_pair = dict.fromkeys(range(league_start, league_end + 1), 0)
        self.league_ID = league_ID
        self.lineups = {}

    def __str__(self):

        return self.owner_name
    
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

    def __init__(self, league_start, league_end, league_ID, sql_db):

        self.league_start = league_start
        self.league_end = league_end
        self.league_ID = league_ID
        self.db = sql_db
        self.player_manifest = {}
        self.owners = self.populate_owners()
        self.seasons = self.populate_seasons()
        self.test_seasons()
                
    def populate_owners(self):
        # Populate owners 
        # looks at each year of fantasy league and gets an owner ID for each season
        
        preamble = 'http://games.espn.go.com/ffl/leaguesetup/ownerinfo?leagueId='
        postID = '&seasonId='

        driver = webdriver.Firefox()
        owners = {}

        for year in range(self.league_start, self.league_end + 1):
            url = preamble + str(self.league_ID) + postID + str(year)
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
                                self.league_end, self.league_ID
                                )
                        try:
                            owners[name].set_year_ID(year, iter_owner)
                        except:
                            continue                                            
                    except:
                        continue

        driver.close()
        return owners

    def populate_seasons(self):

        return [
            Season(year, self) for year 
            in range(self.league_start, self.league_end + 1)
            ]

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
                id_2010, id_2011, id_2012, id_2013, id_2014, id_2015) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', payload
                )

        conn.commit()
        conn.close()

    def test_seasons(self):
        for season in self.seasons:
            for game in season.playoff_games:
                if game.game_type == 'Championship':
                    print game.winner


class Season(object):
    # The Season object will hold league results for a given season
    # Regular season and postseason data will be collected differently
    # Final standings will be determined

    def __init__(self, year, league):

        self.year = year
        self.league = league
        self.season_length = 0
        self.regular_games, self.playoff_games = self.populate_games()

    def populate_games(self):

        games = []
        #URL elements
        pre = 'http://games.espn.com/ffl/schedule?leagueId='
        post = '&seasonId='
        url = pre + str(self.league.league_ID) + post + str(self.year)

        schedule_tree = html.fromstring(requests.get(url).text)
        schedule_table = schedule_tree.xpath('//table[@class="tableBody"]')[0]

        week = 0

        #iterate through regular season weeks and games
        for row in schedule_table.xpath('.//tr'):
            if not row.xpath('./td') or row.xpath('./td[1]/text()')[0].replace(u'\xa0', u' ') == ' ':
                continue
            elif 'PLAYOFF' in row.xpath('./td/text()')[0]:
                break
            elif 'WEEK' in row.xpath('./td/text()')[0]:
                week += 1
                continue
            else:
                games.append(Game(
                    'Regular',
                    self.league.owners[str(row.xpath('./td[2]/text()')[0])],
                    self.league.owners[str(row.xpath('./td[5]/text()')[0])],
                    self, week
                    )
                )

        self.season_length = week #set number of games in season

        return games, self.populate_playoffs(schedule_table)

    def populate_playoffs(self, schedule_table):

        playoff_games = []

        schedule_table = schedule_table

        for playoff_round, playoff_week in enumerate(
            schedule_table.xpath('//td[contains(text(),"ROUND")]'), 1
            ):
            if playoff_round == 1:
                wild_one = playoff_week.xpath('../following-sibling::tr[2]')[0]
                wild_two = playoff_week.xpath('../following-sibling::tr[3]')[0]
                for game in [wild_one, wild_two]:
                    playoff_games.append(Game(
                    'Wild-card',
                    self.league.owners[str(game.xpath('./td[2]/text()')[0])],
                    self.league.owners[str(game.xpath('./td[5]/text()')[0])],
                    self, self.season_length + playoff_round
                    )
                )

            elif playoff_round == 2:
                semi_one = playoff_week.xpath('../following-sibling::tr[2]')[0]
                semi_two = playoff_week.xpath('../following-sibling::tr[3]')[0]
                for game in [semi_one, semi_two]:
                    playoff_games.append(Game(
                    'Semi-final',
                    self.league.owners[str(game.xpath('./td[2]/text()')[0])],
                    self.league.owners[str(game.xpath('./td[5]/text()')[0])],
                    self, self.season_length + playoff_round
                    )
                )

            else:
                championship = playoff_week.xpath('../following-sibling::tr[2]')[0]
                third_place = playoff_week.xpath('../following-sibling::tr[3]')[0]
                fifth_place = playoff_week.xpath('../following-sibling::tr[4]')[0]
                games = [championship, third_place, fifth_place]
                for game, game_type in zip(
                    games, ['Championship', '3rd Place', '5th Place']):
                    playoff_games.append(Game(
                    game_type,
                    self.league.owners[str(game.xpath('./td[2]/text()')[0])],
                    self.league.owners[str(game.xpath('./td[5]/text()')[0])],
                    self, self.season_length + playoff_round
                    )
                )
        return playoff_games

class Game(object):
    # Game class contains information a single game between two teams

    def __init__(self, game_type, away_owner, home_owner, season, week):

        self.game_type = game_type
        self.away_owner = away_owner
        self.home_owner = home_owner
        self.league = season.league
        self.season = season
        self.week = week
        self.away_lineup, self.home_lineup = self.populate_lineups()
        self.result = self.get_scores()
        self.winner = self.determine_winner()

    def populate_lineups(self):

        payload = (
            self.league.league_ID, 
            self.away_owner.year_ID_pair[self.season.year], 
            self.week, self.season.year
            )
        pre = 'http://games.espn.com/ffl/boxscorequick?'
        variable = 'leagueId=%s&teamId=%s&scoringPeriodId=%s&seasonId=%s' % payload
        post = '&view=scoringperiod&version=quick'
        url = pre + variable + post

        game_tree = html.fromstring(requests.get(url).text)

        for table, owner in enumerate([self.away_owner, self.home_owner]):
            table_id = 'playertable_%s' % table
            lineup_table = game_tree.get_element_by_id(table_id)
            owner.lineups[self.season.year, self.week] = []
            for player in lineup_table.xpath('.//td[@class="playertablePlayerName"]/parent::tr'):
                
                if self.season.year == 2015:
                    player_name = player.xpath(
                        './td[@class="playertablePlayerName"]/a[1]/text()'
                        )[0]
                    player_ID = player.xpath('./@id')[0]
                    position_line = player.xpath('./td[@class="playertablePlayerName"]/text()')[0]
                    position = position_line[position_line.rfind(u'\xa0')+1:]
                else:
                    demographics = player.xpath(
                        './td[@class="playertablePlayerName"]/text()'
                        )[0]
                    player_ID = player.xpath('./@id')[0]
                    player_name = demographics[:demographics.find(',')]
                    position = demographics[demographics.rfind(u'\xa0') + 1:]
                
                try:
                    points_line = player.xpath(
                        './td[@class="playertableStat appliedPoints"]/text()')[0]
                    if points_line == '--':
                        points = 0.0
                    else:
                        points = float(points_line)

                except:
                    points = float(player.xpath(
                        './td[@class="playertableStat appliedPoints appliedPointsProGameFinal"]/text()')[0])


                if player_ID not in list(self.league.player_manifest.iterkeys()):
                    self.league.player_manifest[player_ID] = Player(player_ID, player_name, position)

                player = self.league.player_manifest[player_ID]
                player.games[self.season.year, self.week] = (self, points)

                owner.lineups[self.season.year, self.week].append(player)

        return [
            self.away_owner.lineups[self.season.year, self.week], 
            self.home_owner.lineups[self.season.year, self.week]
            ]

    def get_scores(self):

        scores = []

        for owner in [self.away_owner, self.home_owner]:
            score = 0
            for player in owner.lineups[self.season.year, self.week]:
                score += player.games[self.season.year, self.week][1]
            scores.append(score)

        return scores

    def determine_winner(self):
        
        if self.result[0] > self.result[1]:
            return self.away_owner
        elif self.result[1] > self.result[0]:
            return self.home_owner
        else:
            return None

    def roster_test(self):
        print self.result
        print self.away_owner
        print self.home_owner
        print self.season.year
        print self.week

class Player(object):

    def __init__(self, player_ID, player_name, position):

        self.player_ID = player_ID
        self.player_name = player_name
        self.position = position
        self.games = {}

    def __str__(self):

        return self.player_name + ', ' + self.position



def main(league_start, league_end, league_ID, sql_db):

    new_league = League(league_start, league_end, league_ID, sql_db)


main(2007, 2015, 392872, 'sphs_friends.sqlite')       