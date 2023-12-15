# -*- coding: utf-8 -*-
"""
Created on Fri Aug  11 11:43:23 2023

@author: Otto Milvang, sjakk@milvang.no
"""
import json
import sys
import math
import rating as rating


"""
Structre 

+--- tiebreaks: [  - added in compute-tiebreak
|         {
|             order: priority of tiebreak
|             name: Acronym from regulations
|             pointtype: mpoints (match points) gpoints (game points) or points 
|             modifiers: { low / high / lim / urd / p4f / fmo / rb5 / z4h / vuv }
|         }, 
|         ...
|    
|       ]
+--- isteam: True/False
+--- currentRound: Standings after round 'currentround'
+--- rounds: Total number of rounds
+--- rr: RoundRobin (True/False)
+--- scoresystem: {
|        game: { W:1.0, D:0.5, L:0.0, Z:0.0, P:1.0, A:0.5, U: 0.0 }
|        team: { W:1.0, D:1.0, L:0.0, Z:0.0, P:1.0, A:1.0, U: 0.0 }
|                 }
+--- players/teams:  {
|              1: {
|                    cid: startno
|                    rating: rating
|                    kfactor: k
|                    rating: rating
|                    rrst: {  - results, games for players, matches for teams
|                        1: {  - round
|                              points - points for game / match
|                              rpoints - for games, points with score system 1.0 / 0.5 / 0.0 
|                              color - w / b 
|                              played  - boolean
|                              rated - boolean
|                              opponent - id of opponent
|                              opprating - rating of opponent
|                              deltaR - for rating change
|                            }
|                        2: {  - round 2 }
|                           ...
|                           }
|                   tbval: {  - intermediate results from tb calculations }
|     ---- output for each player / team
|                   score: [ array of tie-breaks values, same order and length as 'tiebreaks'
|                   rank: final rank of player / team
|                 },
|              2: { ... },
|                  ...
|         }
+--- rankorder: [ array of rankorder,  players/teams ]  
|
                                 
"""


class tiebreak:

    

    # constructor function    
    def __init__(self, chessevent, tournamentno):
        event = chessevent.event
        tournament = chessevent.get_tournament(tournamentno)
        self.tiebreaks = []
        self.isteam = self.isteam = tournament['teamTournament'] if 'teamTournament' in tournament else False
        self.currentround = 0
        self.rounds = tournament['numRounds']
        self.get_score = chessevent.get_score
        self.maxboard = 0
        self.primaryscore = None # use default

        self.scoreList = {}
        for name, scoresystem in chessevent.scoreList.items():
            self.scoreList[name] = scoresystem
        for scoresystem in event['scoreLists']:
            for key, value in scoresystem['scoreSystem'].items():
                self.scoreList[scoresystem['listName']][key] = value
        if self.isteam:
            self.teamscore = tournament['teamSection']['scoreSystem']
            self.gamescore = tournament['playerSection']['scoreSystem']
            [self.cplayers, self.cteam] = chessevent.build_tournament_teamcompetitors(tournament)
            self.allgames = chessevent.build_all_games(tournament, self.cteam, False)    
            self.teams = self.prepare_competitors(tournament['teamSection'], 'match')
            self.compute_score(self.teams, 'mpoints', self.teamscore, self.currentround)
            self.compute_score(self.teams, 'gpoints', self.gamescore, self.currentround)
        else:
            self.teamscore = tournament['playerSection']['scoreSystem']
            self.gamescore = tournament['playerSection']['scoreSystem']
            self.players = self.prepare_competitors(tournament['playerSection'], 'game')
            self.compute_score(self.players, 'points', self.gamescore, self.currentround)            
        self.cmps = self.teams if self.isteam  else self.players
        numcomp = len(self.cmps)
        self.rankorder = list(self.cmps.values()) 

        if 'currentRound' in tournament:
            self.currentround = tournament['currentRound']
        
        # find tournament type
        tt = tournament['tournamentType'].upper()
        self.rr = False
        if tt.find('SWISS') >= 0:
            self.rr = False
        elif tt.find('RR') >= 0 or tt.find('ROBIN') >= 0 or tt.find('BERGER') >= 0: 
            self.rr = True
        elif numcomp == self.rounds + 1 or numcomp == self.rounds:
                self.rr = True
        elif numcomp == (self.rounds + 1)*2 or numcomp == self.rounds * 2:
            self.rr = True

   
    
    def prepare_competitors(self, competition, scoretype):
        rounds = self.currentround
        #scoresystem = self.scoresystem['match']

        cmps = {}
        for competitor in competition['competitors']:
            cmp = {
                    'cid': competitor['cid'],
                    'rsts': {},
                    'orgrank': competitor['rank'],
                    'rank': 1,
                    'rating': (competitor['rating'] if 'rating' in competitor else 0),
                    'tieBreak': [],
                    'tbval': {}
                  }
            cmps[competitor['cid']] = cmp
        for rst in competition['results']: 
            rounds = self.prepare_result(cmps, rst, self.teamscore, rounds)
            if self.isteam:
                self.prepare_teamgames(cmps, rst, self.gamescore)
        self.currentround = rounds
        with open('C:\\temp\\cmps.json', 'w') as f:
            json.dump(cmps, f, indent=2)

        return cmps

    def prepare_result(self, cmps, rst, scoresystem, rounds):
        ptype = 'mpoints' if self.isteam else 'points'
        rnd = rst['round']
        white = rst['white']
        wPoints = self.get_score(scoresystem, rst, 'white')
        wrPoints = self.get_score('rating', rst, 'white')
        wrating = 0
        brating = 0
        expscore = None
        if 'black' in rst:
            black = rst['black']
        else:
            black = 0
        if  black > 0:
            if not 'bResult' in rst:
                rst['bResult'] = self.scoreList['reverse'][rst['wResult']]
            bPoints = self.get_score(scoresystem, rst, 'black')
            brPoints = self.get_score('rating', rst, 'black')
            if (rst['played']):
                if 'rating' in cmps[white] and cmps[white]['rating'] > 0:
                    wrating = cmps[white]['rating']
                if 'rating' in cmps[black] and cmps[black]['rating'] > 0:
                    brating = cmps[black]['rating']
                expscore = rating.ComputeExpectedScore(wrating, brating)
                
        cmps[white]['rsts'][rnd] = {
            ptype: wPoints, 
            'rpoints': wrPoints, 
            'color': 'w', 
            'played': rst['played'], 
            'rated': rst['rated'] if 'rated' in rst else (rst['played'] and black > 0), 
            'opponent': black,
            'opprating': brating,
            'board': rst['board'],
            'deltaR': (rating.ComputeDeltaR(expscore, wrPoints) if not expscore == None else None  ) 
            } 
        if (black> 0):
            if rnd > rounds:
                rounds = rnd
            cmps[black]['rsts'][rnd] = {
                ptype: bPoints, 
                'rpoints': brPoints, 
                'color': "b", 
                'played': rst['played'], 
                'rated': rst['rated']  if 'rated' in rst else (rst['played'] and white > 0),
                'opponent': white,
                'opprating': wrating,
                'board': rst['board'],
                'deltaR': (rating.ComputeDeltaR(1.0-expscore, brPoints) if not expscore == None else None  ) 
                }
        return rounds

    def prepare_teamgames(self, cmps, rst, scoresystem):
        maxboard = 0
        rnd = rst['round']
        for col in ['white', 'black']:
            if col in rst and rst[col] > 0:
                gpoints = 0
                competitor = rst[col]
                games = []
                for game in self.allgames[rnd][competitor]:
                    white = game['white']
                    black = game['black'] if 'black' in game else 0
                    maxboard = max(maxboard, game['board'])
                    if self.cteam[white] == competitor:
                        points = self.get_score(self.gamescore, game, 'white')
                        gpoints += points
                        games.append(
                            {
                                'points': points,
                                'rpoints': self.get_score('rating', game, 'white'),
                                'color': 'w',
                                'played': game['played'],
                                'rated' : game['rated'] if 'rated' in rst else (game['played'] and black > 0), 
                                'player': white,
                                'opponent': black,
                                'board': game['board']
                            }) 
                    if black > 0 and self.cteam[black] == competitor:
                        points = self.get_score(self.gamescore, game, 'black')
                        gpoints += points
                        games.append(
                            {
                                'points': points,
                                'rpoints': self.get_score('rating', game, 'black'),
                                'color': 'b',
                                'played': game['played'],
                                'rated' : game['rated'] if 'rated' in rst else (game['played'] and black > 0), 
                                'player': black,
                                'opponent': white,
                                'board': game['board']
                            })
                cmps[competitor]['rsts'][rnd]['gpoints'] = gpoints
                cmps[competitor]['rsts'][rnd]['games'] = games
        self.maxboard = max(self.maxboard, maxboard)
    
    
    def compute_score(self, cmps, pointtype, scoretype, rounds):
#        scoresystem = self.scoresystem[scoretype]
        prefix = pointtype + "_" 
        for startno, cmp in cmps.items():
            tbscore = cmp['tbval']
            tbscore[prefix + 'sno'] = startno
            tbscore[prefix + 'rank'] = cmp['orgrank'];
            tbscore[prefix + 'num'] = 0    # number of elements
            tbscore[prefix + 'lo'] = 0     # last round with opponent
            tbscore[prefix + 'lp'] = 0     # last round played 
            tbscore[prefix + 'points'] = 0 # total points
            tbscore[prefix + 'pfp'] = 0    # points from played games
            tbscore[prefix + 'win'] = 0    # number of wins (played and unplayed)
            tbscore[prefix + 'won'] = 0    # number of won games over the board
            tbscore[prefix + 'bpg'] = 0    # number of black games played
            tbscore[prefix + 'bwg'] = 0    # number of games won with black
            tbscore[prefix + 'ge'] = 0     # number of games played + PAB
            tbscore[prefix + 'lg'] = self.scoreList[scoretype]['D'] # Result of last game
            tbscore[prefix + 'bp'] = {}    # Boardpoints
            for rnd, rst in cmp['rsts'].items():
                # total score
                points = rst[pointtype]
                tbscore[prefix + 'points'] += points
                # number of games
                if self.isteam and scoretype == 'game':
                    gamelist = rst['games']
                else:
                    gamelist = [rst]
                for game in gamelist:
                    if self.isteam and scoretype == 'game':
                        points = game['points']
                        board = game['board'];
                        tbscore[prefix + 'bp'][board] = tbscore[prefix + 'bp'][board]  + points if board in tbscore[prefix + 'bp']  else points
                    tbscore[prefix + 'num'] += 1
                    # last round with opponent, pab or fpb (16.2.1, 16.2.2, 16.2.3 and 16.2.4)
                    if rnd > tbscore[prefix + 'lo'] and (game['played'] or game['opponent'] > 0 or points == self.scoreList[scoretype]['W']):
                        tbscore[prefix + 'lo'] = rnd
                    # points from played games    
                    if game['played'] and game['opponent'] > 0:
                        tbscore[prefix + 'pfp'] += points
                    # last played game (or PAB)
                    if rnd > tbscore[prefix + 'lp'] and game['played']:
                        tbscore[prefix + 'lp'] = rnd
                    # number of win
                    if points == self.scoreList[scoretype]['W']:
                        tbscore[prefix + 'win'] += 1
                    # number of win played over the board
                    if points == self.scoreList[scoretype]['W'] and game['played']:
                        tbscore[prefix + 'won'] += 1
                    # number of games played with black
                    if game['color'] == 'b' and game['played']:
                        tbscore[prefix + 'bpg'] += 1
                    # number of win played with black
                    if game['color'] == 'b' and game['played'] and points == self.scoreList[scoretype]['W']:
                        tbscore[prefix + 'bwg'] += 1
                    # number of games elected to play
                    if game['played'] or (game['opponent'] > 0 and points == self.scoreList[scoretype]['W']):
                        tbscore[prefix + 'ge'] += 1
                    # result in last game
                    if rnd == self.rounds and game['opponent'] > 0:
                        tbscore[prefix + 'lg'] = points 


    def compute_recursive_if_tied(self, tb, cmps, rounds, compute_singlerun):
        (points, scoretype, prefix) = self.get_scoreinfo(tb, True)
        name = tb['name'].lower()
        ro = self.rankorder
        for player in ro:
            player['tbval'][prefix + name] = player['rank']  # rank value initial value = rank
            player['tbval']['moreloops'] = True  #  As long as True we have more to check
        loopcount = 0
        moretodo = compute_singlerun(tb, cmps, rounds, ro, loopcount)
        while moretodo:
            moretodo = False
            loopcount += 1
            start = 0;
            while start < len(ro):
                currentrank = ro[start]['tbval'][prefix + name]
                for stop in range( start+1,  len(ro)+1):
                    if stop == len(ro) or currentrank !=  ro[stop]['tbval'][prefix + name]:
                        break
                # we have a range start .. stop-1 to check for top board result
                if ro[start]['tbval']['moreloops']:
                    if stop - start == 1:
                        moreloops = False
                        ro[start]['tbval']['moreloops'] = moreloops
                    else:
                        subro = ro[start:stop] # subarray of rankorder
                        moreloops = compute_singlerun(tb,cmps, rounds, subro, loopcount) 
                        for player in subro:
                            player['tbval']['moreloops'] = moreloops  # 'de' rank value initial value = rank
                        moretodo = moretodo or moreloops
                start = stop            
            #json.dump(ro, sys.stdout, indent=2)
            ro = sorted(ro, key=lambda p: (p['rank'], p['tbval'][prefix + name], p['cid']))
            
        # reorder 'tb' 
        start = 0;
        while start < len(ro):
            currentrank = ro[start]['rank']
            for stop in range( start,  len(ro)+1):
                if stop == len(ro) or currentrank !=  ro[stop]['rank']:
                    break
                # we have a range start .. stop-1 to check for direct encounter
            offset = ro[start]['tbval'][prefix + name]
            if ro[start]['tbval'][prefix + name] != ro[stop-1]['tbval'][prefix + name]:
                offset -=1 
            for p in range(start, stop):
                ro[p]['tbval'][prefix + name] -= offset
            start = stop
        return name

           


    def compute_singlerun_direct_encounter(self, tb, cmps, rounds, subro, loopcount):
        name = tb['name'].lower()
        (points, scoretype, prefix) = self.get_scoreinfo(tb, True)
        if loopcount == 0:
            tb['modifiers']['points'] = points
            tb['modifiers']['scoretype'] = scoretype
            return True
        points = tb['modifiers']['points'] 
        scoretype = tb['modifiers']['scoretype'] 
        changes = 0
        currentrank = subro[0]['tbval'][prefix + name]
        metall = True          # Met all opponents on same range
        metmax = len(subro)-1  # Max number of opponents
        for player in range(0, len(subro)):
            de = subro[player]['tbval']
            de['denum'] = 0    # number of opponens
            de['deval'] = 0    # sum score against of opponens
            de['demax'] = 0    # sum score against of opponens, unplayed = win
            de['delist'] = { }  # list of results numgames, score, maxscore 
            for rnd, rst in subro[player]['rsts'].items():
                if rnd <= rounds:
                    opponent = rst['opponent']
                    if opponent > 0:
                          played = True if tb['modifiers']['p4f'] else rst['played']
                          if played and cmps[opponent]['tbval'][prefix + name] == currentrank:
                              # 6.1.2 compute average score 
                              if opponent in de['delist']:
                                  score = de['delist'][opponent]['score']
                                  num = de['delist'][opponent]['num']
                                  sumscore = score * num
                                  de['deval'] -= score
                                  num += 1
                                  sumscore += rst['points']
                                  score = sumscore / num
                                  de['denum'] = 1
                                  de['deval'] += score
                                  de['delist'][opponent]['num'] = 1 
                                  de['delist'][opponent]['score'] = score
                              else:
                                  de['denum'] += 1
                                  de['deval'] += rst[points]
                                  de['delist'][opponent] = { 'num': 1,
                                                             'score': rst[points]
                                                            }
            #if not tb['modifiers']['p4f'] and de['denum'] < metmax:
            if (not tb['modifiers']['p4f'] and de['denum'] < metmax) or tb['modifiers']['sws']:
                metall = False
                de['demax'] = de['deval'] + (metmax - de['denum']) * self.scoreList[scoretype]['W']
            else:
                de['demax'] = de['deval']
        if metall: # 6.2 All players have met
            subro = sorted(subro, key=lambda p: (-p['tbval']['deval'], p['cid']))
            rank = subro[0]['tbval'][prefix + name]
            val = subro[0]['tbval']['deval']
            for i in range(1, len(subro)):
                rank += 1
                if (val != subro[i]['tbval']['deval']):
                    subro[i]['tbval'][prefix + name] = rank
                    val = subro[i]['tbval']['deval']
                    changes += 1
                else:
                    subro[i]['tbval'][prefix + name] = subro[i-1]['tbval'][prefix + name]
        else: # 6.2 swiss tournament
            subro = sorted(subro, key=lambda p: (-p['tbval']['deval'], -p['tbval']['demax'], p['cid']))
            rank = subro[0]['tbval'][prefix + name]
            val = subro[0]['tbval']['deval']
            unique = True
            for i in range(1, len(subro)):
                rank += 1
                if (unique and val > subro[i]['tbval']['demax']):
                    subro[i]['tbval'][prefix + name] = rank
                    val = subro[i]['tbval']['deval']
                    changes += 1
                else:
                    subro[i]['tbval'][prefix + name] = subro[i-1]['tbval'][prefix + name]
                    unique = False
        if changes == 0 and tb['name'] == 'EDE':
            (points, scoretype, prefix) = self.get_scoreinfo(tb, True)
            if points == tb['modifiers']['points']:
                tb['modifiers']['points'] = self.reverse_pointtype(points)
                tb['modifiers']['scoretype'] = self.teamscore if tb['modifiers']['points'][0] == 'm' else self.gamescore
                changes = 1
        return changes > 0 and loopcount < 30

        

    def copmute_progressive_score(self, tb, cmps, rounds):
        (points, scoretype, prefix) = self.get_scoreinfo(tb, True)
        low = tb['modifiers']['low'] 
        for startno, cmp in cmps.items():
            tbscore = cmp['tbval']
            ps = 0
            for rnd in range(low, rounds+1):
                p = cmp['rsts'][rnd][points] if rnd in cmp['rsts'] else 0.0
                ps += p * (rounds+1-rnd)
            tbscore[prefix + 'ps'] = ps
        return 'ps'
              

    def copmute_koya(self, tb, cmps, rounds):
        (points, scoretype, prefix) = self.get_scoreinfo(tb, True)
        lim = tb['modifiers']['lim'] 
        for startno, cmp in cmps.items():
            tbscore = cmp['tbval']
            ks = 0
            for rnd, rst in cmp['rsts'].items():
                if rnd <= rounds:
                    opponent = rst['opponent']
                    if opponent > 0:
                        if cmps[opponent]['tbval'][prefix + points] * low + 0.000001  >= 100 * scoresystem['W']*rounds:
                            ks += cmp['tbval'][prefix + points] 
            tbscore[prefix + 'ks'] = ks
        return 'ks'


            
    def compute_buchholz_sonneborn_berger(self, tb, cmps, rounds):
        (opoints, oscoretype, oprefix) = self.get_scoreinfo(tb, True)
        (spoints, sscoretype, sprefix) = self.get_scoreinfo(tb, True)
        name = tb['name'].lower()
        if name == 'aob': 
            name = 'bh'
        is_sb = name == 'sb' or name == 'esb'
        if name == 'esb':
            (spoints, sscoretype, sprefix) = self.get_scoreinfo(tb, False)
        for startno, cmp in cmps.items():
            tbscore = cmp['tbval']
            # 16.3.2    Unplayed rounds of category 16.2.5 are evaluated as draws.
            tbscore[oprefix + 'ownbh'] = 0
            for rnd, rst in cmp['rsts'].items():
                if rnd <= tbscore[oprefix + 'lo']:
                    tbscore[oprefix + 'ownbh'] += rst[opoints]
            tbscore[oprefix + 'ownbh'] = tbscore[oprefix + 'ownbh'] + (rounds - tbscore[oprefix + 'lo']) * self.scoreList[oscoretype]['D']  # own score used for bh
            if name == 'fb' and tbscore[oprefix + 'lo'] == self.rounds:
                tbscore[oprefix + 'ownbh'] = tbscore[oprefix + 'ownbh'] - tbscore[oprefix + 'lg'] + self.scoreList[oscoretype]['D']
        for startno, cmp in cmps.items():
            tbscore = cmp['tbval']
            bhvalue = [] 
            for rnd, rst in cmp['rsts'].items():
                if rnd <= rounds:
                    opponent = rst['opponent']
                    if opponent > 0:
                        played = True if tb['modifiers']['p4f'] else rst['played']
                        if played or not tb['modifiers']['urd']:
                            score = cmps[opponent]['tbval'][oprefix + 'ownbh']
                            tbvalue = score * rst[spoints] if is_sb else score
                        else:
                            score = cmps[startno]['tbval'][oprefix + 'ownbh']
                            tbvalue = score * rst[spoints] if is_sb else score
                    else:
                        played = False
                        score = cmps[startno]['tbval'][oprefix + 'ownbh'] 
                        tbvalue = score * rst[spoints] if is_sb else score
                    bhvalue.append({'played': played, 'tbvalue': tbvalue, 'score': score}) 
            # add unplayed rounds
            for x in range(len(bhvalue), rounds):
                score = tbscore[sprefix + 'ownbh'] 
                tbvalue = 0.0 if is_sb else score
                bhvalue.append({'played': played, 'tbvalue': tbvalue, 'score': score}) 
            low = tb['modifiers']['low'] 
            if low > rounds:
                low = rounds 
            high = tb['modifiers']['high']
            if low + high > rounds: 
                high = rounds - low 
            while low > 0:
                sortall = sorted(bhvalue, key=lambda game: (game['score'], game['tbvalue']))
                sortexp = sorted(bhvalue, key=lambda game: (game['played'], game['score'], game['tbvalue']))
                if (tb['modifiers']['vun'] or sortall[0]['tbvalue'] > sortexp[0]['tbvalue']):
                    bhvalue = sortall[1:]
                else:
                    bhvalue = sortexp[1:]
                low -= 1
            if high > 0:
                if tb['modifiers']['vun']:
                    bhvalue = sorted(bhvalue, key=lambda game: (-game['score'], -game['tbvalue']))[high:]
                else:
                    bhvalue = sorted(bhvalue, key=lambda game: (game['played'], -game['score'], -game['tbvalue']))[high:]
            tbscore = cmp['tbval']
            tbscore[oprefix + name] = 0   
            for game in bhvalue:
                tbscore[oprefix + name] += game['tbvalue']
        return name

    def compute_ratingperformance(self, tb, cmps, rounds):
        (points, scoretype, prefix) = self.get_scoreinfo(tb, True)
        for startno, cmp in cmps.items():
            rscore = 0
            ratingopp = []
            for rnd, rst in cmp['rsts'].items():
                if rnd <= rounds and rst['played'] and rst['opprating'] > 0:
                    rscore += rst['rpoints']
                    ratingopp.append(rst['opprating'])
            cmp['tbval'][prefix + 'aro'] = rating.ComputeAverageRatingOpponents(ratingopp)
            cmp['tbval'][prefix + 'tpr'] = rating.ComputeTournamentPerformanceRating(rscore, ratingopp)
            cmp['tbval'][prefix + 'ptp'] = rating.ComputePerfectTournamentPerformance(rscore, ratingopp)
        return tb['name'].lower()


    def compute_boardcount(self, tb, cmps, rounds):
        (points, scoretype, prefix) = self.get_scoreinfo(tb, True)
        for startno, cmp in cmps.items():
            tbscore = cmp['tbval']
            bc = 0
            for val, points in tbscore[prefix + 'bp'].items():
                bc += val * points
            tbscore[prefix + 'bc'] = bc
        return 'bc'

    def compute_singlerun_topbottomboardresult(self, tb, cmps,  rounds, ro, loopcount):
        (points, scoretype, prefix) = self.get_scoreinfo(tb, True)
        if loopcount == 0:
            for player in ro:
                player['tbval'][prefix + 'tbr'] = 0
                player['tbval'][prefix + 'bbe'] = player['tbval'][prefix + 'points']
            return True
        for player in range(0, len(ro)):
            ro[player]['tbval'][prefix + 'tbr'] = ro[player]['tbval']['gpoints_' + 'bp'][loopcount]
            ro[player]['tbval'][prefix + 'bbe'] -= ro[player]['tbval']['gpoints_' + 'bp'][self.maxboard - loopcount +1]
        return loopcount < self.maxboard

    def compute_score_Strength_combination(self, tb, cmps, currentround):
        (points, scoretype, prefix) = self.get_scoreinfo(tb, True)
        for startno, cmp in cmps.items():
            dividend = cmp['tbval'][prefix + 'sssc']
            divisor = 1 
            key = points[0]
            if key == 'm':
                score = cmp['tbval']["gpoints_" + 'points']    
                divisor = math.floor(self.scoreList[scoretype]['W'] * currentround / self.scoreList[self.gamescore]['W'] / self.maxboard)
            elif key == 'g':
                score = cmp['tbval']["mpoints_" + 'points']    
                divisor = math.floor(self.scoreList[scoretype]['W'] * currentround *  self.maxboard / self.scoreList[self.teamscore]['W'])
            cmp['tbval'][prefix + 'sssc'] = score + dividend / divisor
        
        return 'sssc'


 

    def reverse_pointtype(self, txt):
        match txt:
            case 'mpoints':
                return 'gpoints'
            case 'gpoints':
                return 'mpoints'
            case 'mmpoints':
                return 'ggpoints'
            case 'mgpoints':
                return 'gmpoints'
            case 'gmpoints':
                return 'mgpoints'
            case 'ggpoints':
                return 'mmgpoints'
        return txt
      
    def parse_tiebreak(self,  order, txt):
        #BH@23:IP#C1-P4F
        txt = txt.upper()
        comp = txt.split('#')
        if len(comp) == 1:
            comp = txt.split('-')
        nameparts = comp[0].split(':')
        name = nameparts[0]
        scoretype = 'x'
        if self.primaryscore != None:
            pointtype = self.primaryscore    
        elif self.isteam:
            pointtype = 'mpoints'                         
        else:    
            pointtype = 'points'                         
        if len(nameparts) == 2:
            match nameparts[1].upper():
                case 'MP':
                    pointtype = 'mpoints'
                case 'GP':
                    pointtype = 'gpoints'
                case 'MM':
                    pointtype = 'mmpoints'
                case 'MG':
                    pointtype = 'mgpoints'
                case 'GM':
                    pointtype = 'gmpoints'
                case 'GG':
                    pointtype = 'ggpoints'
        if self.primaryscore == None and name == "PTS":
            self.primaryscore = pointtype
        #if name == 'MPVGP':
        #    name = 'PTS'
        #        pointtype = self.reverse_pointtype(self.primaryscore)

        modifiers = []  
        if len(comp) == 2:
            modifiers = comp[1].split('-')              
        tb = {'order': order,
              'name': name,
              'pointtype': pointtype,
              'modifiers': {'low': 0,
                            'high': 0,
                            'lim': 50,
                            'urd': False,
                            'p4f': self.rr,
                            'sws': False,
                            'fmo': False,
                            'rb5': False,
                            'z4h': False,
                            'vun': False
                            } 
                  }
        for mf in modifiers:
            mf = mf.upper()
            for index in range (0, len(mf)):  
                match mf[index]:
                    case 'C':
                        if mf[1:].isdigit():
                            tb['modifiers']['low'] = int(mf[1:])
                    case 'M':
                        if mf[1:].isdigit():
                            tb['modifiers']['low'] = int(mf[1:])
                            tb['modifiers']['high'] = int(mf[1:])
                    case 'L':
                        if mf[1:].isdigit():
                            tb['modifiers']['lim'] = int(mf[1:])
                    case 'U':
                        tb['modifiers']['urd'] = True;    
                    case 'P':
                        tb['modifiers']['p4f'] = True;    
                    case 'F':
                        tb['modifiers']['fmo'] = True;    
                    case 'R':
                        tb['modifiers']['rb5'] = True;    
                    case 'S':
                        tb['modifiers']['sws'] = True;    
                    case 'Z':
                        tb['modifiers']['z4h'] = True;    
                    case 'V':
                        tb['modifiers']['vun'] = True;    
#        print(tb)
        return tb
        
    def addval(self, cmps, tb, value):
        (points, scoretype, prefix) = self.get_scoreinfo(tb, True)
        for startno, cmp in cmps.items():
            #print(prefix, scoretype, cmp['tbval'])
            cmp['tieBreak'].append(cmp['tbval'][prefix + value])
            
            

    def compute_average(self, tb, name, cmps, ignorezero):
        (points, scoretype, prefix) = self.get_scoreinfo(tb, True)
        tbname = tb['name'].lower()
        for startno, cmp in cmps.items():
            sum = 0
            num = 0
            for rnd, rst in cmp['rsts'].items():
                if rst['played'] and rst['opponent'] > 0:
                    opponent = rst['opponent']
                    value = cmps[opponent]['tbval'][prefix + name]
                    if not ignorezero or value > 0:
                        num += 1
                        sum += value            
            cmp['tbval'][prefix + tbname] = int(round(sum /num)) if num > 0 else 0
        return tbname
 
    # get_scoreinfo(self, tb, primary)
    # tb - tie break
    # primary or secondary score



    def get_scoreinfo(self, tb, primary):
        pos = 0 if primary else 1;
        key = tb['pointtype'][pos]
        if not primary and (key != 'g' and key != 'm'):
            key = tb['pointtype'][0]
            if (key == 'g'):
                key = 'm'
            elif (key == 'm'):
                key = 'g'
        match tb['pointtype'][pos]:
            case 'g':
                return ["gpoints", self.gamescore, "gpoints_"]
            case 'm':
                return ["mpoints", self.teamscore, "mpoints_"]
            case _:
                return ["points", self.gamescore, "points_"]

                                
    def compute_tiebreak(self, tb):
        cmps = self.cmps
        order = tb['order']
        tbname = ''
        if tb['pointtype'][0] == 'g':
            scoretype = self.gamescore;
        else:
            scoretype = self.teamscore;
        match tb['name']:
            case 'PTS':
                tbname = 'points'
            case 'MPVGP':
                tb['pointtype'] =  self.reverse_pointtype(self.primaryscore)
                tbname = 'points'
            case 'SNO' | 'RANK':
                tb['modifiers']['reverse'] = False
                tbname = tb['name'].lower()
            case 'DF':
                tbname = self.compute_direct_encounter(tb, cmps, self.currentround)
            case 'DE' | 'EDE':
                #tbname = self.compute_direct_encounter(tb, cmps, self.currentround)
                tb['modifiers']['reverse'] = False
                tbname = self.compute_recursive_if_tied(tb, cmps, self.currentround, self.compute_singlerun_direct_encounter)
            case 'WIN' | 'WON' | 'BPG' | 'BWG' | 'GE':
                tbname = tb['name'].lower()
            case 'PS':
                tbname = self.copmute_progressive_score(tb, cmps, self.currentround)
            case 'BH' | 'FB' | 'SB':
                tbname = self.compute_buchholz_sonneborn_berger(tb, cmps, self.currentround)
            case 'AOB':
                tbname = self.compute_buchholz_sonneborn_berger(tb, cmps, self.currentround)
                tbname = self.compute_average(tb, 'bh', cmps, True)    
            case 'ARO' | 'TPR' | 'PTP' :
                tbname = self.compute_ratingperformance(tb, cmps, self.currentround)
            case 'APRO' :
                tbname = self.compute_ratingperformance(tb, cmps, self.currentround)
                tbname = self.compute_average(tb, 'tpr', cmps, True)    
            case 'APPO':
                tbname = self.compute_ratingperformance(tb, cmps, self.currentround)
                tbname = self.compute_average(tb, 'ptp', cmps, True)
            case 'ESB':
                tbname = self.compute_buchholz_sonneborn_berger(tb, cmps, self.currentround)
            case'BC':
                tb['modifiers']['reverse'] = False
                scoretype = self.gamescore;
                tbname = self.compute_boardcount(tb, cmps, self.currentround)
            case'TBR' | 'BBE':
                tb['modifiers']['reverse'] = False
                scoretype = self.gamescore;
                tbname = self.compute_recursive_if_tied(tb, cmps, self.currentround, self.compute_singlerun_topbottomboardresult)
            case'SSSC':
                tbname = self.compute_buchholz_sonneborn_berger(tb, cmps, self.currentround)
                tbname = self.compute_score_Strength_combination(tb, cmps, self.currentround)
            case _:
                tbname = None
                return

        self.tiebreaks.append(tb)
        index = len(self.tiebreaks) - 1 
        self.addval(cmps, tb, tbname)
        reverse = 1 if 'reverse' in tb['modifiers'] and not tb['modifiers']['reverse'] else -1
        #for cmp in self.rankorder:
        #    print(index, cmp['tieBreak'][index])
        self.rankorder = sorted(self.rankorder, key=lambda cmp: (cmp['rank'], cmp['tieBreak'][index]*reverse, cmp['cid']))
        rank = 1
        val = self.rankorder[0]['tieBreak'][index]
        for i in range(1, len(self.rankorder)):
            rank += 1
            if (self.rankorder[i]['rank'] == rank or self.rankorder[i]['tieBreak'][index] != val):
                self.rankorder[i]['rank'] = rank
                val = self.rankorder[i]['tieBreak'][index]
            else:
                self.rankorder[i]['rank'] = self.rankorder[i-1]['rank']
        #for i in range(0,len(self.rankorder)):
        #    t = self.rankorder[i]
        #    print(t['cid'], t['rank'], t['score'])
        #json.dump(self.cmps, sys.stdout, indent=2)
                    
                    
        