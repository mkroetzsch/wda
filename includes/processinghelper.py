#!/usr/bin/python
# -*- coding: utf-8 -*-

# Helper class to parse dump data, including some very simple caches for better reuse
class ProcessingHelper:

	daysUntilMonth = ( 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334 )

	def __init__(self):
		self.valRev = False
		self.val = False
		self.dateInfoStamp = False
		self.dateInfo = False

	def getVal(self, rev, rawContent):
		if rev != self.valRev:
			self.val = eval(rawContent.replace('":null', '":0').replace('&quot;', '"'))
			if 'claims' not in self.val: # make sure this is always set
				self.val['claims'] = []
			if 'description' not in self.val or not self.val['description']: # make sure this is always set and a dictionary
				self.val['description'] = {}
			if 'aliases' not in self.val or not self.val['aliases']: # make sure this is always set and a dictionary
				self.val['aliases'] = {}
			if 'links' not in self.val or not self.val['links']: # make sure this is always set and a dictionary
				self.val['links'] = {}
			if 'label' not in self.val or not self.val['label']: # make sure this is always set and a dictionary
				self.val['label'] = {}
			self.valRev = rev
		return self.val

	def getDateInfo(self, dateInfoStamp):
		if self.dateInfoStamp != dateInfoStamp:
			year = int(dateInfoStamp[0:4])
			month = int(dateInfoStamp[5:7])
			day = int(dateInfoStamp[8:10])
			self.dateInfoStamp = dateInfoStamp
			self.dateInfo = (year,month,day,self.getWDDay(year,month,day))
		return self.dateInfo

	def getWDDay(self,year,month,day):
		if month>2 and year%4 == 0 : # we omit the 100 and 400 year exceptions for this script ;-)
			leapYear = 1
		else:
			leapYear = 0
		return (year-2012)*365 + int((year-2009)/4) + ProcessingHelper.daysUntilMonth[month-1] + leapYear + day - 1

	def getYMDFromWDDay(self,wdday):
		fullYears = int(wdday/365) # since 2012
		leapYears = int((fullYears+3)/4)
		# leap year correction:
		if (wdday - fullYears*365 - leapYears)<0:
			fullYears -= 1
			leapYears = int((fullYears+3)/4)

		dayOfYear = wdday - fullYears*365 - leapYears
		month = 0
		leapYearDay = 0
		while month < 12 and dayOfYear >= ProcessingHelper.daysUntilMonth[month] + leapYearDay:
			month += 1
			if month == 2 and fullYears%4 == 0:
				leapYearDay = 1
		if month == 2:
			leapYearDay = 0

		return (fullYears+2012, month, dayOfYear-ProcessingHelper.daysUntilMonth[month-1]-leapYearDay + 1)