#!/usr/bin/python
# -*- coding: utf-8 -*-

import os, urllib, re, gzip, bz2
import logging

# Class for fetching and managing MediaWiki dump files.
# If can download required dumps (and daily dumps) and produce
# a list of the relevant files for other components to process.
# Main entry points are getNewerDailyDates(), getDailyFile(),
# getLatestDumpFile(), and (easiest) processRecentDumps().
class DataFetcher:

	# Constructor.
	#
	# offline: bool, if True then only previously downloaded dumps will be used
	# current: bool, if True then dumps with only current versions instead of full history will be used
	#
	# Note that "current" only affects which main dump to get, without any
	# impact on the dailies. Processors therefore must never assume that
	# the data contains only one (most recent) revision of each file.
	def __init__(self, offline = False, current = False):
		self.basePath = os.getcwd()
		self.dailies = False
		self.newerdailies = False # Dates of dailies that are more recent than the dump
		self.latestdump = False
		self.maxrevid = False
		self.stopdaily = False
		self.offline = offline
		self.maxdumpdate = 'ANYTIME' # only consider dates before that time (ANYTIME sorts after all real dates)
		# Select which main dump files to get
		if current:
			self.dumpPostFix = '-pages-meta-current.xml.bz2'
			self.dumpDirName = 'curdump'
			self.dumpFileName = 'pages-meta-current.xml.bz2'
			self.dumpName = 'dump of current revisions'
		else:
			self.dumpPostFix = '-pages-meta-history.xml.bz2'
			self.dumpDirName = 'dump'
			self.dumpFileName = 'pages-meta-history.xml.bz2'
			self.dumpName = 'dump of all revisions'
		# Note: to find existing directories easily, the dirname
		# must not be a prefix of any other possible dirname.

	# Set another maximal date for dumps to consider.
	# The date should be formatted as YYYYMMDD.
	def setMaxDumpDate(self,date):
		self.maxdumpdate = date

	# Find out which daily dump files are available, either locally or online.
	def getDailyDates(self):
		if not self.dailies:
			self.dailies = []
			if self.offline:
				logging.logMore("Finding daily exports available locally ")
				dataDirs = os.listdir("data")
				for dirName in dataDirs:
					if not dirName.startswith('daily'): continue
					date = dirName[5:]
					if not re.match('\d\d\d\d\d\d\d\d', date) : continue
					logging.logMore('.')
					self.dailies.append(date)
				self.dailies = sorted(self.dailies)
			else:
				logging.logMore("Finding daily exports online ")
				for line in urllib.urlopen('http://dumps.wikimedia.org/other/incr/wikidatawiki/') :
					if not line.startswith('<tr><td class="n">') : continue
					date = line[27:35]
					if not re.match('\d\d\d\d\d\d\d\d', date) : continue
					logging.logMore('.')
					self.dailies.append(date)
			logging.log(" found " + str(len(self.dailies)) + " daily exports.")
		return self.dailies

	# Return the most recent date up to which data is available.
	def getLatestDate(self):
		nds = self.getNewerDailyDates()
		if nds:
			return nds[0]
		else:
			return self.getLatestDumpDate()

	# Convenience method to iterate over all available dump data,
	# most recent first, using the given processor.
	def processRecentDumps(self,dumpProcessor):
		if self.latestdump == '00000000':
			logging.log('*** Warning: no latest ' + self.dumpName + ' found.\n*** Analysing dailies only now.\n*** Results might be incomplete.')
		for daily in self.getNewerDailyDates() :
			logging.log('Analysing daily ' + daily + ' ...')
			try:
				file = self.getDailyFile(daily)
				dumpProcessor.processFile(file)
				file.close()
			except EOFError as e:
				logging.log('*** Error while reading file (' + str(e) + ").\n" + '*** Try deleting the daily directory for ' + daily + ' and download a new version.')
				file.close()

		# Finally also process the latest main dump:
		if self.latestdump == '00000000':
			logging.log('*** Warning: no latest ' + self.dumpName + ' found.')
		else:
			logging.log('Analysing latest ' + self.dumpName + ' ' + self.getLatestDumpDate() + ' ...')
			file = self.getLatestDumpFile()
			dumpProcessor.processFile(file)
			file.close()

	# Find out when the last successful dump happened, and which is not later
	# than self.maxdumpdate.
	def getLatestDumpDate(self):
		if not self.latestdump:
			self.latestdump = '00000000'
			if self.offline:
				logging.logMore('Checking for the date of the last local ' + self.dumpName + ' ')
				dataDirs = os.listdir("data")
				for dirName in dataDirs:
					if not dirName.startswith(self.dumpDirName): continue
					date = dirName[len(self.dumpDirName):]
					if not re.match('\d\d\d\d\d\d\d\d', date) : continue
					logging.logMore('.')
					if date > self.latestdump and date <= self.maxdumpdate:
						self.latestdump = date
			else:
				logging.logMore('Checking for the date of the last online ' + self.dumpName + ' ')
				for line in urllib.urlopen('http://dumps.wikimedia.org/wikidatawiki/') :
					if not line.startswith('<tr><td class="n">') : continue
					date = line[27:35]
					if not re.match('\d\d\d\d\d\d\d\d', date) : continue
					logging.logMore('.')
					#logging.log("Checking dump of " + date)
					# check if dump is finished
					finished = False
					for md5 in urllib.urlopen('http://dumps.wikimedia.org/wikidatawiki/' + date + '/wikidatawiki-' + date + '-md5sums.txt') :
						if md5.endswith(self.dumpPostFix + "\n") :
							finished = True
							break
					if finished and date > self.latestdump and date <= self.maxdumpdate:
						self.latestdump = date

			if self.latestdump == '00000000':
				logging.log('-- Warning: no latest ' + self.dumpName + ' found.')
			else:
				logging.log(' latest ' + self.dumpName + ' is ' + self.latestdump)
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
		if self.latestdump == '00000000': # no offline dump found
			self.maxrevid = 0
			return # give up
		# The rest we do even in offline mode to get the latest revision id:

		self.__cdData()
		if not os.path.exists(self.dumpDirName + self.latestdump) :
			os.makedirs(self.dumpDirName + self.latestdump)
		os.chdir(self.dumpDirName + self.latestdump)

		if not os.path.exists('site_stats.sql.gz') :
			logging.log('Downloading stats of the latest dump (' + self.latestdump + ') ...')
			urllib.urlretrieve('http://dumps.wikimedia.org/wikidatawiki/' + self.latestdump + '/wikidatawiki-' + self.latestdump + '-site_stats.sql.gz', 'site_stats.sql.gz')
		else:
			logging.log('Stats of the latest dump (' + self.latestdump + ') found. No download needed.')

		# download the latest dump if needed
		if not os.path.exists(self.dumpFileName) :
			logging.log('Downloading latest ' + self.dumpName + ' ...')
			urllib.urlretrieve('http://dumps.wikimedia.org/wikidatawiki/' + self.latestdump + '/wikidatawiki-' + self.latestdump + self.dumpPostFix, self.dumpFileName) #xxx
		else:
			logging.log('Latest ' + self.dumpName + ' (' + self.latestdump + ') found. No download needed.')

		if not self.maxrevid:
			for line in gzip.open('site_stats.sql.gz'):
				if not line.startswith('INSERT INTO') : continue
				stats = eval(line[32:-2])
				self.maxrevid = int(stats[2])
				break
		logging.log('Maximal revision id of the latest ' + self.dumpName + ': ' + str(self.maxrevid))

		self.__cdBase()

	# Download all available daily dump files that are newer than the latest dump,
	# but not more recent than self.maxdumpdate.
	# In offline mode, this will only consider dailies for which there is a local
	# directory already. Assuming proper donwloads happened earlier, no further
	# download will be needed.
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

			if daily > self.maxdumpdate:
				logging.log('too recent to consider')
				os.chdir('..')
				continue

			if not os.path.exists('maxrevid.txt') :
				maxrevSource = 'http://dumps.wikimedia.org/other/incr/wikidatawiki/' + daily + '/maxrevid.txt'
				urllib.urlretrieve(maxrevSource, 'maxrevid.txt')
			else:
				maxrevSource = 'Local Max Rev File'
			
			try:
				dailymaxrevid = int(open('maxrevid.txt').read())
			except ValueError:
				#This happens if a daily dump failed?
				logging.log(maxrevSource + ' throws ValueError')

			if daily < self.getLatestDumpDate() :
				logging.log('already in latest ' + self.dumpName)
				self.stopdaily = daily
				os.chdir('..')
				break

			if not os.path.exists('pages-meta-hist-incr.xml.bz2') :
				if self.offline:
					logging.log('not downloading daily in offline mode')
				else:
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
		if self.latestdump == '00000000':
			logging.log('*** Error: no latest ' + self.dumpName + ' found.')
			return None
		else:
			self.__cdData()
			os.chdir(self.dumpDirName + self.latestdump)
			file = bz2.BZ2File(self.dumpFileName)
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
