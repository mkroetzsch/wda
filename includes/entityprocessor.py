#!/usr/bin/python
# -*- coding: utf-8 -*-

# Abstract class to be used as template for implementing EPs.
class EntityProcessor:

	# Main method for processing the data of one item.
	#
	# title: string; e.g. Q42
	# revision: integer
	# isItem: bool; false for properties and true for items
	# data: dictionary with the actual data
	def processEntity(self,title,revision,isItem,data):
		pass

	# Print information about the progress of processing.
	# All outputs that are logged in this method should be
	# preceded by the string '     * '.
	def logReport(self):
		pass

	# Finish processing (e.g., to add a footer and close files)
	def close(self):
		pass