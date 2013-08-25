#!/usr/bin/python
# -*- coding: utf-8 -*-
from bitarray import bitarray
from includes import processinghelper, database


class DBCurrentAnalyzer:

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

