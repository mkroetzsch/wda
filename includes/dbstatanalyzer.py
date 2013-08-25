#!/usr/bin/python
# -*- coding: utf-8 -*-

import database
import processinghelper
import logging
import time
import bitarray

# Class to analyse previously created database contents for historic
# statistics.
#
# TODO This code is very specific to one kind of report and should
# probably get a different name.
class DBStatAnalyzer:
	def __init__(self):
		self.helper = processinghelper.ProcessingHelper()
		self.db = database.Database()

		self.dayStats = {}
		self.totalItems = 0
		self.startTime = 0

		self.processeditems = bitarray.bitarray(2**26) # about 30 M items
		self.processeditems.setall(0)

	def close(self):
		self.db.closeDatabase()

	def getDays(self):
		logging.logMore("Getting days: ")
		cur = self.db.query("SELECT DISTINCT(day) FROM itemrevstats ORDER BY day ASC",())
		self.days = []
		print "Days: " + str(cur.rowcount)
		row = cur.fetchone()
		while row:
			self.days.append(int(row[0]))
			logging.logMore(str(row[0]) + ' ')
			row = cur.fetchone()
		cur.close()
		logging.log("... done")

	def getEmptyDayStats(self):
		return { 'items': 0, 'changeditems':0, 'stats':0, 'statsr':0, 'statsq':0,\
			'links':0, 'labels':0, 'descs':0, 'aliases':0 }

	def makeStatistics(self):
		self.startTime = time.time()
		self.getDays()
		#self.days = [447]
		prevDay = -1
		for day in self.days:
			if prevDay == -1:
				self.dayStats[day] = self.getEmptyDayStats()
			else:
				self.dayStats[day] = self.dayStats[prevDay].copy()
				self.dayStats[day]['changeditems'] = 0
			prevDay = day

			logging.logMore("Fetching data for day " + str(day))
			cur = self.db.query("SELECT * FROM itemrevstats WHERE day=%s",(day))
			logging.log(" ... done.")

			row = cur.fetchone()
			while row:
				if not self.processeditems[int(row[0])]:
					isNewEntity = True
					self.processeditems[int(row[0])] = True
					self.dayStats[day]['items'] += 1
				else:
					isNewEntity = False

				self.updateStats(row,isNewEntity,day)

				self.dayStats[day]['changeditems'] += 1
				self.totalItems += 1
				if self.totalItems % 100000 == 0:
					print "Processed " + str(self.totalItems) + " items in " + str(round(time.time() - self.startTime,2)) + " sec. Current data:\n" + str(self.dayStats[day])

				row = cur.fetchone()

			print "Processed " + str(self.totalItems) + " items. Final data:\n" + str(self.dayStats)
			# Close the cursor (this is essential) ...
			cur.close()
			# ... and be paranoid about memory leaks (may not have much effect)
			del cur
			self.db.reopenDatabase()

	def updateStats(self,row,isNewEntity,day):
		self.addStats(row,day,1)
		if not isNewEntity:
			cur = self.db.query("SELECT * FROM itemrevstats WHERE id=%s AND day<%s ORDER BY day DESC LIMIT 1",(row[0],day))
			oldrow = cur.fetchone()
			if oldrow:
				self.addStats(oldrow,day,-1)

	def addStats(self,row,day,factor=1):
		self.dayStats[day]['stats'] += factor * row[5]
		self.dayStats[day]['statsr'] += factor * row[6]
		self.dayStats[day]['statsq'] += factor * row[7]
		self.dayStats[day]['labels'] += factor * row[8]
		self.dayStats[day]['descs'] += factor * row[9]
		self.dayStats[day]['links'] += factor * row[10]
		self.dayStats[day]['aliases'] += factor * row[11]

	def writeResultSums(self, file):
		file.write("date,total items,edited items,statements,statements w refs,statements w qualifiers,labels,descriptions,links,aliases\n")
		for day in self.days:
			ymd = self.helper.getYMDFromWDDay(day)
			file.write( "{0[0]:d}-{0[1]:02d}-{0[2]:02d},".format(ymd) )
			file.write( str(self.dayStats[day]['items']) + ',')
			file.write( str(self.dayStats[day]['changeditems']) + ',')
			file.write( str(self.dayStats[day]['stats']) + ',')
			file.write( str(self.dayStats[day]['statsr']) + ',')
			file.write( str(self.dayStats[day]['statsq']) + ',')
			file.write( str(self.dayStats[day]['labels']) + ',')
			file.write( str(self.dayStats[day]['descs']) + ',')
			file.write( str(self.dayStats[day]['links']) + ',')
			file.write( str(self.dayStats[day]['aliases']) + "\n")