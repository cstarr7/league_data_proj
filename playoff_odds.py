# -*- coding: utf-8 -*-
"""
Created on Tue Dec 01 20:17:32 2015

@author: Charlie
"""

from lxml import html
import requests
import string
import numpy as np
import random
import copy
import csv
import pandas as pd


class Owner(object):
    #create an owner class for every owner in the standings table

    def __init__(self, name_complex, ID, wins, losses, rank):
        #initialize variables that will be needed for simulation
        self.name_complex = name_complex
        self.ID = ID
        self.wins = wins
        self.losses = losses
        self.current_rank = rank        
        self.scores = []
        self.win_percentage = 0.00
        self.total_points = 0
        self.average_points = 0
        self.points_stdev = 0
        self.final_opponents = []
        
    def schedule_data(self, league_id):
        #get info about games played and games remaining
        schedule_url = ('http://games.espn.go.com/ffl/schedule?leagueId='
            + league_id + '&teamId=' + self.ID + '&seasonId=2016'
            )
        raw_schedule = requests.get(schedule_url)
        html_schedule = html.fromstring(raw_schedule.text)

        for index, score in enumerate(html_schedule.xpath('//nobr/a/text()'), 0):
            if not 'Box' in score:
                score = float(score[string.find(score, ' ') 
                    + 1:string.find(score, '-')]
                    )
                self.scores.append(score)
            else:
                self.final_opponents.append(html_schedule.xpath(
                    '//a[@target="_top"]/@title')[index]
                )

        score_array = np.array(self.scores)
        self.total_points = np.sum(score_array)
        self.average_points = np.mean(score_array)
        self.points_stdev = np.std(score_array)
        self.calc_win_percentage()

        return
    
    def calc_win_percentage(self):

        self.win_percentage = float(self.wins)/len(self.scores)
    
    def __cmp__(self, other):

        if self.win_percentage > other.win_percentage:
            return 1
        elif self.win_percentage < other.win_percentage:
            return -1
        elif self.total_points > other.total_points:
            return 1
        elif self.total_points < other.total_points:
            return -1
        else:
            return 0
                
    def __str__(self):

        return self.name_complex
    

class SimulationOwner(Owner):
    #a copy of each owner is created for each simulation
    
    def __init__(self, owner): #passing owners from ownerlist for temporary sim class

        self.name_complex = owner.name_complex
        self.wins = owner.wins
        self.losses = owner.losses      
        self.scores = copy.deepcopy(owner.scores)
        self.total_points = owner.total_points
        self.average_points = owner.average_points
        self.points_stdev = owner.points_stdev
        self.final_opponents = owner.final_opponents
        self.simulated_points = self.simulate_point_total() #simulated point total
        self.final_rank = 0
    
    def simulate_point_total(self):

        simulated_points = []
        for game in self.final_opponents:
            simulated_points.append(random.gauss(
                self.average_points, self.points_stdev
                )
            )
        self.total_points += sum(simulated_points)
        self.scores.extend(simulated_points)
        return simulated_points

class Simulation(object):

    def __init__(self, owner_list, rank_table):

        self.simulated_owners = {owner.name_complex:SimulationOwner(owner) 
            for owner in owner_list
            }
        self.rank_table = rank_table
        self.play_games()
        self.simulated_rankings = sorted(self.simulated_owners.values(),
            reverse = True
            )
        self.wild_card()
        self.update_table()

    def play_games(self):

        for sim_owner in self.simulated_owners.itervalues():         
            for index, week_simulation in enumerate(sim_owner.simulated_points):
                opponent = self.simulated_owners[sim_owner.final_opponents[index]]
                if week_simulation > self.simulated_owners[opponent.name_complex].simulated_points[index]:
                    sim_owner.wins += 1
                elif week_simulation < self.simulated_owners[opponent.name_complex].simulated_points[index]:
                    sim_owner.losses += 1
            sim_owner.calc_win_percentage()

        return

    def wild_card(self):

        wild_card = max(self.simulated_rankings[5:], key = lambda sim_owner: sim_owner.total_points)
        wild_card = self.simulated_rankings.pop(self.simulated_rankings.index(wild_card))
        self.simulated_rankings.insert(5, wild_card)
        return

    def update_table(self):

        for rank, sim_owner in enumerate(self.simulated_rankings, 1):
            self.rank_table[rank][sim_owner.name_complex] += 1            

def populate_owners(league_id):

    owner_list = []    
    standings_url = ('http://games.espn.go.com/ffl/standings?leagueId=' +
                    league_id + '&seasonId=2016')
    raw_standings = requests.get(standings_url)
    html_standings = html.fromstring(raw_standings.text)
    rank = 1
    for standings_entry in html_standings.xpath('//tr[@class="tableBody"]'):   
        name_complex = standings_entry.xpath('./td/a[@title]/@title')[0]
        id_reference = standings_entry.xpath('./td/a[@title]/@href')[0]
        ID = id_reference[string.find(id_reference, 'teamId='):]
        ID = ID[7:string.find(ID, '&seasonId=')]
        wins = int(standings_entry.xpath('./td[2]/text()')[0])
        losses = int(standings_entry.xpath('./td[3]/text()')[0])
        new_owner = Owner(name_complex, ID, wins, losses, rank)
        new_owner.schedule_data(league_id)
        owner_list.append(new_owner)
        rank += 1
    return owner_list
    
def build_table(owner_list):

    table = pd.DataFrame(0, index = [owner.name_complex for owner in owner_list],
        columns = ['Current'] + range(1, len(owner_list) + 1))
    table.index.name = 'Team'
    table['Current'] = range(1, len(owner_list) + 1)
    return table

def calculate_percentages(tally_table, number):

    tally_table.ix[:, 1:] = tally_table.ix[:, 1:] / float(number) * 100
    return tally_table

def main():
    
    league_id = raw_input('Please enter your league ID number?')
    sim_number = int(raw_input('How many times do you want to sim the remaining games?'))
    owner_list = populate_owners(league_id)
    owner_list.sort(reverse=True)
    standings_table = build_table(owner_list)
    for i in range(1, sim_number+1):
        if i%1000 == 0:
            print i
        Simulation(owner_list, standings_table)
    percentage_table = calculate_percentages(standings_table, sim_number)
    writer = pd.ExcelWriter('simout_3.xlsx')
    percentage_table.to_excel(writer)
    writer.save()

main()
    
    
    
   
    
        
    