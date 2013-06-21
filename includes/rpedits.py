#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
import revisionprocessor
import urllib

# Count user/bot edits per day
class RPEditCount(revisionprocessor.RevisionProcessor):
	def __init__(self,helper):
		self.helper = helper
		self.botEdits = {}
		self.humanEdits = {}
		self.anonEdits = {}
		self.botTotal = 0
		self.humanTotal = 0
		self.anonTotal = 0
		self.curMin = 100000000
		self.curMax = -100000000

		self.editsByUser = {}

		logging.logMore('Loading list of bots ')
		self.bots = []
		botsjson = urllib.urlopen('http://www.wikidata.org/w/api.php?action=query&list=allusers&augroup=bot&aulimit=500&format=json').read()
		botsdata = eval(botsjson)
		for bot in botsdata['query']['allusers'] :
			self.bots.append(bot['name'])
			logging.logMore('.')
		logging.log(' found ' + str(len(self.bots)) + ' bot accounts.')

	def startPageBlock(self,title,isItem,isNew):
		revisionprocessor.RevisionProcessor.startPageBlock(self,title,isItem,isNew)

	def processRevision(self,revId,timestamp,user,isIp,rawContent):
		timeInfo = self.helper.getDateInfo(timestamp[:10])
		wdday = timeInfo[3]
		self.curMin = min(wdday,self.curMin)
		self.curMax = max(wdday,self.curMax)
		if wdday not in self.humanEdits:
			self.humanEdits[wdday] = 0
			self.botEdits[wdday] = 0
			self.anonEdits[wdday] = 0
		if isIp:
			self.anonEdits[wdday] += 1
			self.anonTotal += 1
		elif user in self.bots:
			self.botEdits[wdday] += 1
			self.botTotal += 1
		else:
			self.humanEdits[wdday] += 1
			self.humanTotal += 1

		# The following code counts edits by user.
		# One can put it into an if block to restrict
		# to edits on a particular day.
		if isIp:
			userKey = user + 'I'
		else:
			userKey = user + 'U'
		if userKey not in self.editsByUser:
			self.editsByUser[userKey] = 0
		self.editsByUser[userKey] += 1


	def logReport(self):
		logging.log('     * Total edits: ' + str(self.botTotal + self.anonTotal + self.humanTotal) + ' (' + str(self.botTotal) + ' bots, ' + str(self.humanTotal) + ' humans, ' + str(self.anonTotal) + ' anons)')
		logging.log('     * User accounts logged: ' + str(len(self.editsByUser)) )


	def writeResults(self, file):
		file.write("index,date,bots,humans,anons,total\n")
		if not self.humanEdits: # nothing to write
			return
		minDay = min(self.humanEdits.keys())
		maxDay = max(self.humanEdits.keys())
		for i in xrange(minDay, maxDay + 1):
			file.write(str(i))
			file.write(',')
			ymd = self.helper.getYMDFromWDDay(i)
			file.write( "{0[0]:d}-{0[1]:02d}-{0[2]:02d},".format(ymd) )

			if i in self.humanEdits:
				file.write( str(self.botEdits[i]) + ',' )
				file.write( str(self.humanEdits[i]) + ',' )
				file.write( str(self.anonEdits[i]) + ',' )
				file.write( str(self.botEdits[i] + self.humanEdits[i] + self.anonEdits[i]) + "\n" )
			else:
				file.write( "0,0,0,0\n" )


	def writeEditsByUser(self, file):
		file.write("user,ip,bot,edits\n")
		for key in self.editsByUser:
			username = key[:-1]
			ip = key[-1:]
			file.write(username.replace(',','<comma>'))
			file.write(',')
			if ip == 'I':
				file.write('yes,no,')
			else:
				file.write('no,')
				if username in self.bots:
					file.write('yes,')
				else:
					file.write('no,')
			file.write( str(self.editsByUser[key]) )
			file.write("\n")
