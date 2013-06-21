#!/usr/bin/python
# -*- coding: utf-8 -*-

import os, urllib, re, gzip, bz2
import logging

# Class for fetching and managing MediaWiki dump files.
# If can download required dumps (and daily dumps) and produce
# a list of the relevant files for other components to process.
# Main entry points are getNewerDailyDates(), getDailyFile(),
# and getLatestDumpFile().
class DataFetcher:
	def __init__(self):
		self.basePath = os.getcwd()
		self.dailies = False
		self.newerdailies = False # Dates of dailies that are more recent than the dump
		self.latestdump = False
		self.maxrevid = False
		self.stopdaily = False
		# For testing; setting this avoids delays due to http requests:
		#self.dailies = ['20130511', '20130512', '20130513', '20130514', '20130515', '20130516', '20130517', '20130518', '20130519', '20130520', '20130521', '20130522', '20130523', '20130524', '20130525', '20130526', '20130527', '20130528', '20130529', '20130530', '20130531', '20130601']
		#self.latestdump = '20130514'

	# Find out which daily dump files are available on the Web.
	def getDailyDates(self):
		if not self.dailies:
			logging.logMore("Fetching information about available daily exports ")
			self.dailies = []
			for line in urllib.urlopen('http://dumps.wikimedia.org/other/incr/wikidatawiki/') :
				if not line.startswith('<tr><td class="n">') : continue
				date = line[27:35]
				if not re.match('\d\d\d\d\d\d\d\d', date) : continue
				logging.logMore('.')
				self.dailies.append(date)
			logging.log(" found " + str(len(self.dailies)) + " daily exports.")
		return self.dailies

	# Find out when the last successful dump happened.
	def getLatestDumpDate(self):
		if not self.latestdump:
			logging.logMore('Checking for the date of the last dump ')
			self.latestdump = '20121026'
			for line in urllib.urlopen('http://dumps.wikimedia.org/wikidatawiki/') :
				if not line.startswith('<tr><td class="n">') : continue
				date = line[27:35]
				if not re.match('\d\d\d\d\d\d\d\d', date) : continue
				logging.logMore('.')
				#logging.log("Checking dump of " + date)
				# check if dump is finished
				finished = False
				for md5 in urllib.urlopen('http://dumps.wikimedia.org/wikidatawiki/' + date + '/wikidatawiki-' + date + '-md5sums.txt') :
					if md5.endswith('-pages-meta-history.xml.bz2' + "\n") :
						finished = True
				if finished :
					self.latestdump = date
			logging.log(" latest dump has been on " + self.latestdump)
		return self.latestdump

	# Change to the data directory.
	def __cdData(self):
		self.__cdBase()
		if not os.path.exists('data') :
			os.makedirs('data')
		os.chdir('data')

	# Change back to the base directory.
	def __cdBase(self):
		os.chdir(self.basePath)

	# Download the latest dump file, unless it is already available locally.
	def fetchLatestDump(self):
		self.getLatestDumpDate()
		self.__cdData()

		if not os.path.exists('dump' + self.latestdump) :
			os.makedirs('dump' + self.latestdump)
		os.chdir('dump' + self.latestdump)

		if not os.path.exists('site_stats.sql.gz') :
			logging.log('Downloading stats of the latest dump (' + self.latestdump + ') ...')
			urllib.urlretrieve('http://dumps.wikimedia.org/wikidatawiki/' + self.latestdump + '/wikidatawiki-' + self.latestdump + '-site_stats.sql.gz', 'site_stats.sql.gz')
		else:
			logging.log('Stats of the latest dump (' + self.latestdump + ') found. No download needed.')

		# download the latest dump if needed
		if not os.path.exists('pages-meta-history.xml.bz2') :
			logging.log('Downloading latest dump ...')
			urllib.urlretrieve('http://dumps.wikimedia.org/wikidatawiki/' + self.latestdump + '/wikidatawiki-' + self.latestdump + '-pages-meta-history.xml.bz2', 'pages-meta-history.xml.bz2') #xxx
		else:
			logging.log('Latest dump (' + self.latestdump + ') found. No download needed.')

		if not self.maxrevid:
			for line in gzip.open('site_stats.sql.gz'):
				if not line.startswith('INSERT INTO') : continue
				stats = eval(line[32:-2])
				self.maxrevid = int(stats[2])
				break
		logging.log('Maximal revision id of the latest dump: ' + str(self.maxrevid))

		self.__cdBase()

	# Download all available daily dump files that are newer than the latest dump.
	def fetchNewerDailies(self):
		self.getDailyDates()
		if not self.maxrevid:
			self.fetchLatestDump()

		self.__cdData()
		self.stopdaily = '20121026'
		self.newerdailies = []
		for daily in reversed(self.dailies) :
			logging.logMore('Checking daily ' + daily + ' ... ')
			if not os.path.exists('daily' + daily) :
				os.makedirs('daily' + daily)
			os.chdir('daily' + daily)

			if not os.path.exists('maxrevid.txt') :
				urllib.urlretrieve('http://dumps.wikimedia.org/other/incr/wikidatawiki/' + daily + '/maxrevid.txt', 'maxrevid.txt')
			dailymaxrevid = int(open('maxrevid.txt').read())

			if dailymaxrevid < self.maxrevid :
				logging.log('already in latest dump')
				self.stopdaily = daily
				os.chdir('..')
				break

			if not os.path.exists('pages-meta-hist-incr.xml.bz2') :
				logging.logMore('downloading ... ')
				if urllib.urlopen('http://dumps.wikimedia.org/other/incr/wikidatawiki/' + daily + '/status.txt').read() == 'done' :
					urllib.urlretrieve('http://dumps.wikimedia.org/other/incr/wikidatawiki/' + daily + '/wikidatawiki-' + daily + '-pages-meta-hist-incr.xml.bz2', 'pages-meta-hist-incr.xml.bz2') #xxx
					logging.log('done')
					self.newerdailies.append(daily)
				else :
					logging.log('daily not done yet; download aborted')
			else:
				logging.log('daily already downloaded')
				self.newerdailies.append(daily)

			os.chdir('..')

		self.__cdBase()

	# Get a list of dates of dailies that are more recent than the latest full dump.
	# The list is ordered to include the most recent dumps at the start of the list.
	# The method ensures that all daily dumps that are included are also available
	# locally (and it might trigger a download if not done yet).
	def getNewerDailyDates(self):
		if not self.newerdailies:
			self.fetchNewerDailies()
		return self.newerdailies

	# Get a file handler for the latest full dump.
	def getLatestDumpFile(self):
		self.__cdData()
		os.chdir('dump' + self.latestdump)
		file = bz2.BZ2File('pages-meta-history.xml.bz2')
		self.__cdBase()
		return file

	# Get a file handler for the daily dump of the given date.
	# There is no error handling; if the file does not exist, an exception will occur.
	def getDailyFile(self,daily):
		self.__cdData()
		os.chdir('daily' + daily)
		#if not os.path.exists('pages-meta-hist-incr.xml.bz2') :
			#logging.log('ERROR: Data for daily ' + daily + ' not available.')
			#os.chdir('../..')
			#return None
		file = bz2.BZ2File('pages-meta-hist-incr.xml.bz2')
		self.__cdBase()
		return file