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
from itertools import chain


class League(object):


    def __init__(self, league_start, league_end, league_ID, sql_db):

        self.league_start = league_start
        self.league_end = league_end
        self.league_ID = league_ID
        self.db = sql_db
    

class LeagueFromWeb(League):
    # League object will be a container for things associated with the
    # league (i.e owners, draft results, etc)

    def __init__(self, league_start, league_end, league_ID, sql_db):

        super(LeagueFromWeb, self).__init__(
            league_start, league_end, league_ID, sql_db
            )
        self.game_types = {
            'Regular': 1,
            'Wild-card': 2,
            'Semi-final': 3,
            'Championship': 4,
            '3rd Place': 5,
            '5th Place': 6
            }
        self.player_manifest = {}
        self.game_ID_generator = db_id_generator()
        self.player_ID_generator = db_id_generator()
        self.owners = self.populate_owners()
        self.seasons = self.populate_seasons()
        self.league_to_db()
                
    def populate_owners(self):
        # Populate owners 
        # looks at each year of fantasy league and gets an owner ID for each season
        
        preamble = 'http://games.espn.go.com/ffl/leaguesetup/ownerinfo?leagueId='
        postID = '&seasonId='

        driver = webdriver.Firefox()
        owners = {}

        owner_db_IDs = db_id_generator()

        for year in range(self.league_start, self.league_end + 1):
            url = preamble + str(self.league_ID) + postID + str(year)
            driver.get(url)
            if 'redir' in driver.current_url:
                sleep(20)
            element_tree = html.fromstring(driver.page_source)

            # unique identifier for each owner for given season is number
            # between 1 and 16 (use 20 to be safe)
            for element in element_tree.iter('span'):
                pre, post = ('ownerspan', '-0')
                for iter_owner in range(1,20):
                    owner_ID = pre + str(iter_owner) + post
                    #try because some owner IDs are not used and will fail
                    try:
                        name = element.get_element_by_id(owner_ID).text_content()
                        if name not in owners.keys():
                            owners[name] = Owner(
                                owner_db_IDs.next(), name, self.league_start, 
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
        #Creates a season object for each year the league was active.
        #Each season object will contain games

        season_IDs = db_id_generator()

        return [
            Season(season_IDs.next(), year, self) for year 
            in range(self.league_start, self.league_end + 1)
            ]

    def league_to_db(self):

        conn = sqlite3.connect(self.db)
        c = conn.cursor()

        self.create_league_table(c)
        self.create_owner_table(c)
        self.create_seasons_table(c)
        self.create_player_table(c)
        self.create_gametype_table(c)
        self.create_game_table(c)
        self.create_performance_table(c)

        conn.commit()
        conn.close()

    def create_league_table(self, c):

        c.execute('''DROP TABLE IF EXISTS league''')

        c.execute(
            '''CREATE TABLE league
            (league_ID INTEGER NOT NULL PRIMARY KEY UNIQUE,
            league_start INTEGER,
            league_end INTEGER)'''
            )

        c.execute(
            '''INSERT INTO league 
            (league_ID, league_start, league_end) VALUES (?, ?, ?)''',
            (self.league_ID, self.league_start, self.league_end)
            )

    def create_owner_table(self, c):

        c.execute('''DROP TABLE IF EXISTS owners''')
        id_string = ''.join(['id_%s INTEGER, ' % x for x in range(self.league_start, self.league_end + 1)])
        table_creation = 'CREATE TABLE owners (owner_ID INTEGER NOT NULL PRIMARY KEY UNIQUE, name  TEXT UNIQUE, '
        to_create = table_creation + id_string[:-2] + ')'
        c.execute(to_create)

        for owner in self.owners.itervalues():
            payload = (owner.owner_ID, owner.owner_name,) + tuple([owner.year_ID_pair[year] for year
                in range(self.league_start, self.league_end + 1)]
                )
            pre_string = 'INSERT INTO owners (owner_ID, name, '
            variable_string = ''.join(['id_%s, ' % x for x in range(self.league_start, self.league_end + 1)])
            post_string = ') VALUES (?, ?, %s)' % ('?, '*len(range(self.league_start, self.league_end + 1)))[:-2]
            to_insert = pre_string + variable_string[:-2] + post_string
            c.execute(to_insert, payload)

    def create_seasons_table(self, c):

        c.execute('''DROP TABLE IF EXISTS seasons''')

        c.execute(
            '''CREATE TABLE seasons
            (season_ID INTEGER NOT NULL PRIMARY KEY UNIQUE,
            season_year INTEGER,
            season_length INTEGER)'''
            )

        for season in self.seasons:
            c.execute(
                '''INSERT INTO seasons
                (season_ID, season_year, season_length) VALUES (?, ?, ?)''',
                (season.season_ID, season.year, season.season_length)
                )

    def create_player_table(self, c):

        c.execute('''DROP TABLE IF EXISTS players''')

        c.execute(
            '''CREATE TABLE players
            (player_ID INTEGER NOT NULL PRIMARY KEY UNIQUE,
            espn_ID TEXT UNIQUE,
            name TEXT,
            position TEXT)'''
            )

        for player in self.player_manifest.itervalues():
            c.execute(
                '''INSERT INTO players
                (player_ID, espn_ID, name, position) VALUES (?, ?, ?, ?)''',
                (player.player_ID, player.espn_ID,
                player.player_name, player.position)
                )

    def create_gametype_table(self, c):

        c.execute('''DROP TABLE IF EXISTS game_types''')

        c.execute(
            '''CREATE TABLE game_types
            (gametype_ID INTEGER NOT NULL PRIMARY KEY UNIQUE,
            gametype TEXT)'''
            )

        for game_type in self.game_types.iterkeys():
            c.execute(
                '''INSERT INTO game_types (gametype_ID, gametype)
                VALUES (?, ?)''', (self.game_types[game_type], game_type)
                )

    def create_game_table(self, c):

        c.execute('''DROP TABLE IF EXISTS games''')

        c.execute(
            '''CREATE TABLE games
            (game_ID INTEGER NOT NULL PRIMARY KEY UNIQUE,
             game_type TEXT, 
             game_season INTEGER, 
             game_week INTEGER, 
             away_owner INTEGER,
             away_score REAL, 
             home_owner INTEGER,
             home_score REAL, 
             winner INTEGER)'''
             )

        for season in self.seasons:
            for game in chain.from_iterable([season.regular_games, season.playoff_games]):
                payload = (
                    game.game_ID, self.game_types[game.game_type], season.season_ID,
                    game.week, game.away_owner.owner_ID, game.result[0], 
                    game.home_owner.owner_ID, game.result[1], 
                    game.winner
                    )
                print payload
                c.execute(
                    '''INSERT INTO games 
                    (game_ID, game_type, game_season, game_week, away_owner,
                    away_score, home_owner, home_score, winner)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', payload
                     )

    def create_performance_table(self, c):

        c.execute('''DROP TABLE IF EXISTS performances''')

        c.execute(
            '''CREATE TABLE performances
            (performance_ID INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
            player_ID INTEGER,
            performance_year INTEGER,
            performance_week INTEGER,
            performance_owner INTEGER,
            points_scored REAL)'''
            )

        for player in self.player_manifest.itervalues():
            for performance in player.games.itervalues():
                payload = (player.player_ID, performance[0].season.season_ID,
                    performance[0].week, performance[2].owner_ID,
                    performance[1]
                    )

                c.execute(
                    '''INSERT INTO performances 
                    (player_ID, performance_year, 
                    performance_week, performance_owner, points_scored)
                    VALUES (?, ?, ?, ?, ?)''', payload
                    )


class LeagueFromFile(League):


    def __init__(self, league_start, league_end, league_ID, sql_db):

        super(LeagueFromFile, self).__init__(
            league_start, league_end, league_ID, sql_db
            )
        self.game_types = {
            1: 'Regular',
            2: 'Wild-card',
            3: 'Semi-final',
            4: 'Championship',
            5: '3rd Place',
            6: '5th Place'
            }
        self.player_manifest = self.populate_players()
        self.owners = self.populate_owners()
        self.seasons = self.populate_seasons()
        self.test_seasons()

    def populate_players(self):

        players = {}

        conn = sqlite3.connect(self.db)
        c = conn.cursor()

        player_tups = c.execute(
            'SELECT player_ID, espn_ID, name, position FROM players'
            )

        for player in player_tups:
            players[player[0]] = Player(player[0], player[1], player[2], player[3])

        return players

    def populate_owners(self):

        owners = {}

        conn = sqlite3.connect(self.db)
        c = conn.cursor()

        id_columns = ''.join(['id_%s, ' % x for x in range(self.league_start, self.league_end + 1)])
        query_string = 'SELECT owner_ID, name, %s FROM owners' % id_columns[:-2]
        owner_tups = c.execute(query_string)
        
        for owner in owner_tups:
            owners[owner[0]] =  Owner(
                owner[0], owner[1], self.league_start,
                self.league_end, self.league_ID
                )
    
            for year, year_ID in zip(range(self.league_start, self.league_end + 1), owner[2:]):
                owners[owner[0]].set_year_ID(year, year_ID)

        conn.close()

        return owners

    def populate_seasons(self):

        seasons = {}

        conn = sqlite3.connect(self.db)
        c = conn.cursor()

        season_tups = [
            c.execute('SELECT season_ID, season_year, season_length from seasons WHERE season_year = %s' 
            % year).fetchone() for year in range(self.league_start, self.league_end + 1)]

        return {tup[0]:SeasonFromFile(tup[0], tup[1], self, tup[2]) for tup in season_tups}

    def test_seasons(self):
        for year in range(self.league_start, self.league_end + 1):
            for season in self.seasons.itervalues():
                if season.year == year:
                    for game in season.playoff_games:
                        if game.game_type == 'Championship':
                            print game.winner


class Owner(object):
    #class to create object for any manager who has ever played in the league

    def __init__(self, db_ID, name, league_start, league_end, league_ID):
       
        self.owner_ID = db_ID
        self.owner_name = name
        self.year_ID_pair = dict.fromkeys(range(league_start, league_end + 1), 0)
        self.league_ID = league_ID
        self.lineups = {}

    def __str__(self):

        return self.owner_name
    
    def set_year_ID(self, year, ID):
        # Each owner has a unique league ID which is not constant
        
        self.year_ID_pair[year] = ID


class Season(object):
    # The Season object will hold league results for a given season
    # Regular season and postseason data will be collected differently
    # Final standings will be determined

    def __init__(self, season_ID, year, league):

        self.season_ID = season_ID
        self.year = year
        self.league = league
        

class SeasonFromWeb(Season):


    def __init__(self, season_ID, year, league):

        super(SeasonFromWeb, self).__init__(season_ID, year, league)
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
            if not row.xpath('./td') or row.xpath(
                './td[1]/text()')[0].replace(u'\xa0', u' ') == ' ':
                continue
            elif 'PLAYOFF' in row.xpath('./td/text()')[0]:
                break
            elif 'WEEK' in row.xpath('./td/text()')[0]:
                week += 1
                continue
            else:
                games.append(Game(
                    self.league.game_ID_generator.next(), 'Regular',
                    self.league.owners[str(row.xpath('./td[2]/text()')[0])],
                    self.league.owners[str(row.xpath('./td[5]/text()')[0])],
                    self, week
                    )
                )

        self.season_length = week #set number of games in season

        return games, self.populate_playoffs(schedule_table)

    def populate_playoffs(self, schedule_table):

        playoff_games = []

        for playoff_round, playoff_week in enumerate(
            schedule_table.xpath('//td[contains(text(),"ROUND")]'), 1
            ):
            if playoff_round == 1:
                wild_one = playoff_week.xpath('../following-sibling::tr[2]')[0]
                wild_two = playoff_week.xpath('../following-sibling::tr[3]')[0]
                for game in [wild_one, wild_two]:
                    playoff_games.append(Game(
                    self.league.game_ID_generator.next(), 'Wild-card',
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
                    self.league.game_ID_generator.next(), 'Semi-final',
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
                    self.league.game_ID_generator.next(), game_type,
                    self.league.owners[str(game.xpath('./td[2]/text()')[0])],
                    self.league.owners[str(game.xpath('./td[5]/text()')[0])],
                    self, self.season_length + playoff_round
                    )
                )
        return playoff_games

class SeasonFromFile(Season):

    def __init__(self, season_ID, year, league, length):

        super(SeasonFromFile, self).__init__(season_ID, year, league)
        self.season_length = length
        self.regular_games = self.populate_regular()
        self.playoff_games = self.populate_playoffs()

    def populate_regular(self):
        
        conn = sqlite3.connect(self.league.db)
        c = conn.cursor()

        game_tups = c.execute('''SELECT game_ID, game_type, game_season,
            game_week, away_owner, away_score, home_owner, home_score, winner
            from games WHERE game_season = ? and game_type = ?''', (self.season_ID, 1)
            ).fetchall()
        
        return [GameFromFile(
            tup[0], self.league.game_types[int(tup[1])], self.league.owners[tup[4]], 
            self.league.owners[tup[6]], self, tup[3], (tup[5], tup[7]), tup[8]
            ) for tup in game_tups]

        conn.close()

    def populate_playoffs(self):
        conn = sqlite3.connect(self.league.db)
        c = conn.cursor()

        game_tups = c.execute('''SELECT game_ID, game_type, game_season,
            game_week, away_owner, away_score, home_owner, home_score, winner
            from games WHERE game_season = ? and game_type != ?''', (self.season_ID, 1)
            ).fetchall()
        
        return [GameFromFile(
            tup[0], self.league.game_types[int(tup[1])], self.league.owners[tup[4]], 
            self.league.owners[tup[6]], self, tup[3], (tup[5], tup[7]), tup[8]
            ) for tup in game_tups]


class Game(object):
    # Game class contains information a single game between two teams

    def __init__(self, game_ID, game_type, away_owner, home_owner, season, week):

        self.game_ID = game_ID
        self.game_type = game_type
        self.away_owner = away_owner
        self.home_owner = home_owner
        self.league = season.league
        self.season = season
        self.week = week

class GameFromWeb(Game):

    def __init__(self, game_ID, game_type, away_owner, home_owner, season, week):

        super(GameFromWeb, self).__init__(game_ID, game_type, away_owner, home_owner, season, week)
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
            print owner.owner_name
            table_id = 'playertable_%s' % table
            lineup_table = game_tree.get_element_by_id(table_id)
            owner.lineups[self.season.year, self.week] = []
            for player in lineup_table.xpath(
                './/td[@class="playertablePlayerName"]/parent::tr'):
                
                if self.season.year == 2015:
                    player_name = player.xpath(
                        './td[@class="playertablePlayerName"]/a[1]/text()'
                        )[0]
                    player_ID = player.xpath('./@id')[0]
                    position_line = player.xpath(
                        './td[@class="playertablePlayerName"]/text()')[0]
                    position = position_line[position_line.rfind(u'\xa0')+1:]
                else:
                    demographics = player.xpath(
                        './td[@class="playertablePlayerName"]/text()')[0]
                    player_ID = player.xpath('./@id')[0]
                    player_name = demographics[:demographics.find(',')]
                    position = demographics[demographics.rfind(u'\xa0') + 1:]
                print player_name
                print self.season.year
                print self.week
                try:
                    points_line = player.xpath(
                        './td[@class="playertableStat appliedPoints"]/text()')[0]
                    if points_line == '--':
                        points = 0.0
                    else:
                        points = float(points_line)
                except:
                    path = './td[@class="playertableStat appliedPoints appliedPointsProGameFinal"]/text()'
                    points = float(player.xpath(path)[0])

                if player_ID not in list(self.league.player_manifest.iterkeys()):
                    self.league.player_manifest[player_ID] = Player(
                        self.league.player_ID_generator.next(),
                        player_ID, player_name, position
                        )

                player = self.league.player_manifest[player_ID]
                player.games[self.season.year, self.week] = (self, points, owner)

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
            return self.away_owner.owner_ID
        elif self.result[1] > self.result[0]:
            return self.home_owner.owner_ID
        else:
            return 0


class GameFromFile(Game):
    

    def __init__(self, game_ID, game_type, away_owner, home_owner, season, week, result, winner):

        super(GameFromFile, self).__init__(game_ID, game_type, away_owner, home_owner, season, week)
        self.result = result
        self.winner = season.league.owners[winner] if winner != 0 else 'Tie'
        self.away_lineup, self.home_lineup = self.populate_lineups()

    def populate_lineups(self):

        conn = sqlite3.connect(self.season.league.db)
        c = conn.cursor()
        
        for owner in [self.away_owner, self.home_owner]:
            owner.lineups[self.season.year, self.week] = []
            performances = c.execute(
                '''SELECT player_ID, performance_year, performance_week,
                performance_owner, points_scored FROM performances WHERE
                performance_year = ? and
                performance_week = ? and 
                performance_owner = ?''', 
                (self.season.year, self.week, owner.owner_ID)
                )
            for performance in performances:
                player = self.season.league.player_manifest[performance[0]]
                owner.lineups[self.season.year, self.week].append(player)
                player.games[self.season.year, self.week] = (self, performance[3], owner)

        conn.close()

        return [
            self.away_owner.lineups[self.season.year, self.week], 
            self.home_owner.lineups[self.season.year, self.week]
            ]



class Player(object):


    def __init__(self, player_ID, espn_ID, player_name, position):

        self.player_ID = player_ID
        self.espn_ID = espn_ID
        self.player_name = player_name
        self.position = position
        self.games = {}

    def __str__(self):

        return self.player_name + ', ' + self.position

def db_id_generator():

    for i in range(1, 10000):
        yield i

def main(league_start, league_end, league_ID, sql_db):

    #new_league = LeagueFromWeb(league_start, league_end, league_ID, sql_db)
    newer_league = LeagueFromFile(league_start, league_end, league_ID, sql_db)


main(2007, 2015, 392872, 'sphs_friends.sqlite')       