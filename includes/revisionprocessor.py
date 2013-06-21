#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging

# Abstract class to be used as template for implementing RPs.
class RevisionProcessor:
	def __init__(self):
		self.curTitle = False
		self.isItem = False
		self.isNew = False

	# Start to process a block of revisions for a new page.
	# Parameters are:
	#
	# title: string
	# isItem: bool; false for properties and true for items
	# isNew: bool; true if no block for this page has been
	# 	encountered in this run yet
	#
	# It is generally assumed that revisions are processed
	# in reverse chronological order, so the first block that
	# is encountered about a page should contain the most recent
	# revision of that page.
	def startPageBlock(self,title,isItem,isNew):
		self.curTitle = title
		self.isItem = isItem
		self.isNew = isNew

	# Process one revision within the current page block. The method
	# startPageBlock is always called before this. Parameters are:
	#
	# revId: string ID of the revision
	# timestamp: string MW timestamp of the revision
	# user: string MW user name or IP
	# isIP: bool true if the user is an IP, false if it is a registered user
	# rawContent: unprocessed content of this revision
	def processRevision(self,revId,timestamp,user,isIp,rawContent):
		pass

	# Conclude the current page block. The method startPageBlock is
	# always called before this.
	def endPageBlock(self):
		self.curTitle = False

	# Print information about the progress of processing.
	# For even printout, all outputs that are logged in this method should be
	# preceded by the string '     * '.
	def logReport(self):
		pass

# Class to log detailed information about processed data.
# This processor should not be used in normal operation since it creates so much
# output that it will slow down processing.
class RPDebugLogger(RevisionProcessor):
	def startPageBlock(self,title,isItem,isNew):
		RevisionProcessor.startPageBlock(self,title,isItem,isNew)
		if isNew:
			logging.log('Starting page ' + title + ' for the first time ...')
		else:
			logging.log('Starting page ' + title + ' (seen before) ...')

	def processRevision(self,revId,timestamp,user,isIp,rawContent):
		logging.log('Processing rev ' + revId + ' (' + timestamp + ') edited by ' + user + ' (IP: ' + str(isIp) + ').' )

	def endPageBlock(self):
		if self.curTitle:
			logging.log('... finished page ' + self.curTitle + '.')
		RevisionProcessor.endPageBlock(self)

# Gather general statistics for reporting purposes.
# This processor can always be used to do some basic lightweight counting
# without significant performance impact.
class RPStats(RevisionProcessor):
	def __init__(self):
		self.itemCount = 0
		self.propertyCount = 0
		self.newItemCount = 0
		self.newPropertyCount = 0
		self.itemRevisionCount = 0
		self.propertyRevisionCount = 0

	def startPageBlock(self,title,isItem,isNew):
		RevisionProcessor.startPageBlock(self,title,isItem,isNew)
		if isItem:
			self.itemCount += 1
			if isNew:
				self.newItemCount += 1
		else:
			self.propertyCount += 1
			if isNew:
				self.newPropertyCount += 1

	def processRevision(self,revId,timestamp,user,isIp,rawContent):
		if self.isItem:
			self.itemRevisionCount += 1
		else:
			self.propertyRevisionCount += 1

	def endPageBlock(self):
		RevisionProcessor.endPageBlock(self)

	def logReport(self):
		logging.log('     * ' + str(self.itemRevisionCount) + ' revisions of ' + str(self.newItemCount) + ' items (' + str(self.itemCount) + ' blocks of items)')
		logging.log('     * ' + str(self.propertyRevisionCount) + ' revisions of ' + str(self.newPropertyCount) + ' properties (' + str(self.propertyCount) + ' blocks of properties)')


