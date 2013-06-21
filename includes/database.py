#!/usr/bin/python
# -*- coding: utf-8 -*-

import MySQLdb as mdb
import MySQLdb.cursors
import sys
import logging
from ConfigParser import SafeConfigParser

# Class for managing basic database access.
# Database access credentials are currently sought in a
# file wda.ini in the base directory and cannot be injected (sorry).
#
# NOTE The database can become very large when processing Wikidata.
# By default, MySQL will accommodate all data in one file, which grows
# accordingly and will *never* shrink again, even if you delete the
# tables later on. If you want to free your disk space later in your
# life, you must configure MySQL to use one file per table instead,
# using the option innodb_file_per_table. See the Web for details.
class Database:

	def __init__(self):
		self.commitCount = 0
		parser = SafeConfigParser()
		try:
			parser.read('wda.ini')
			self.confUser = parser.get('database', 'user')
			self.confPasswd = parser.get('database', 'passwd')
			self.confHost = parser.get('database', 'host')
			self.confDb = parser.get('database', 'db')
		except:
			print "*** ERROR ***\nDid not find MySQL database configuration. There should be a file\nwda.ini in your base directory.  " +\
				"It should contain something like\nthe following text (you must create the database and user account\nyourself):\n\n" +\
				"[database]\nuser=nameOfYourDatabaseUser\npasswd=passwordOfYourDatabaseUser\ndb=nameOfYourDatabase\nhost=localhost\n"
			sys.exit(1)
		self.openDatabase()

	# Open a connection to the database.
	def openDatabase(self):
		try:
			self.connection = mdb.connect(host=self.confHost, user=self.confUser, passwd=self.confPasswd, db=self.confDb)
			logging.log("Opened connection to database.")
		except mdb.Error, e:
			print "Error %d: %s" % (e.args[0],e.args[1])
			sys.exit(1)

	# Close the connection to the database. If this is not called, some write
	# operations may not be committed.
	def closeDatabase(self):
		if self.connection:
			self.connection.commit()
			self.connection.close()
			del self.connection
			logging.log("Closed connection to database.")

	# Close and reopen database. Can help to free memory with certain cursors.
	def reopenDatabase(self):
		self.closeDatabase()
		self.openDatabase()

	# Log the database version.
	def showVersion(self):
		cur = self.connection.cursor()
		cur.execute("SELECT VERSION()")

		ver = cur.fetchone()

		print "Database version : %s " % ver

	# Delete all tables that are created in createTables().
	# TODO Information on specific tables should be managed in the components that need them.
	def dropTables(self):
		cur = self.connection.cursor()
		logging.log("Dropping database tables ...")
		cur.execute("DROP TABLE IF EXISTS items")
		cur.execute("DROP TABLE IF EXISTS properties")
		cur.execute("DROP TABLE IF EXISTS itemrevstats")
		cur.execute("DROP TABLE IF EXISTS proprevstats")
		logging.log("... finished dropping database tables.")

	# Create tables for several operations.
	# TODO Information on specific tables should be managed in the components that need them.
	def createTables(self):
		cur = self.connection.cursor()
		logging.logMore("Creating database tables ...")
		cur.execute("CREATE TABLE IF NOT EXISTS items(id INT UNSIGNED PRIMARY KEY, \
				rev INT UNSIGNED NOT NULL, \
				claims BLOB, links BLOB, label BLOB, aliases BLOB, description BLOB)")
		cur.execute("CREATE TABLE IF NOT EXISTS properties(id INT UNSIGNED PRIMARY KEY, \
				rev INT UNSIGNED NOT NULL, \
				claims BLOB, datatype VARCHAR(20), label BLOB, aliases BLOB, description BLOB)")
		cur.execute("CREATE TABLE IF NOT EXISTS itemrevstats(id INT UNSIGNED NOT NULL, \
				rev INT UNSIGNED NOT NULL PRIMARY KEY, \
				day SMALLINT UNSIGNED NOT NULL, \
				langinfo BLOB, propinfo BLOB,\
				stat_num SMALLINT UNSIGNED NOT NULL, stat_ref_num SMALLINT UNSIGNED NOT NULL, stat_q_num SMALLINT UNSIGNED NOT NULL,\
				label_num SMALLINT UNSIGNED NOT NULL, desc_num SMALLINT UNSIGNED NOT NULL, link_num SMALLINT UNSIGNED NOT NULL,\
				alias_num SMALLINT UNSIGNED NOT NULL)")
		cur.execute("CREATE UNIQUE INDEX idx_idday ON itemrevstats (id,day)")
		cur.execute("CREATE INDEX idx_day ON itemrevstats (day)")
		cur.execute("CREATE INDEX idx_stat_num ON itemrevstats (stat_num)")
		cur.execute("CREATE TABLE IF NOT EXISTS proprevstats(id INT UNSIGNED NOT NULL, \
				rev INT UNSIGNED NOT NULL PRIMARY KEY, \
				day SMALLINT UNSIGNED NOT NULL, \
				langinfo BLOB, label_num SMALLINT UNSIGNED NOT NULL, desc_num SMALLINT UNSIGNED NOT NULL,\
				alias_num SMALLINT UNSIGNED NOT NULL)")
		cur.execute("CREATE UNIQUE INDEX idx_idday ON proprevstats (id,day)")
		logging.log(" done.")

	# Commit all write activity to the database.
	def commit(self):
		if self.connection:
			self.connection.commit()

	# Execute a query and return the result.
	def query(self,query,fillers):
		cur = self.connection.cursor()
		cur.execute(query,fillers)
		return cur

	# Execute a query and return the result.
	# Uses another cursor to keep results server-side for memory efficiency,
	# but no other queries are possible while the cursor is still open.
	def bigQuery(self,query,fillers):
		cur = self.connection.cursor(MySQLdb.cursors.SSCursor)
		cur.execute(query,fillers)
		return cur

	# Update the data on one item in the items table.
	# TODO Information on specific tables should be managed in the components that need them.
	def updateItemData(self,itemId,rev,claims,links,label,aliases,description):
		cur = self.connection.cursor()
		#curRev = self.getCurrentItemRevision(itemId)
		#if curRev == rev:
			#return None

		cur.execute("""
			INSERT INTO items (id, rev, claims, links, label, aliases, description) VALUES(%s,%s,%s,%s,%s,%s,%s) \
				ON DUPLICATE KEY UPDATE
					rev = VALUES(rev),
					claims = VALUES(claims),
					label = VALUES(label),
					aliases = VALUES(aliases),
					description = VALUES(description)
			""", (itemId,rev,claims,links,label,aliases,description))
		self.__addToCommitCount()
		#print "Number of rows updated:",  cur.rowcount

	# Get current revision stored for an item in the item table.
	# TODO Information on specific tables should be managed in the components that need them.
	def getCurrentItemRevision(self,itemId):
		cur = self.connection.cursor()
		cur.execute("SELECT rev FROM items WHERE id=%s", (itemId))
		res = cur.fetchone()
		if res == None:
			return -1
		else:
			return res[0]

	# Update the data of one property in the properties table.
	# TODO Information on specific tables should be managed in the components that need them.
	def updatePropertyData(self,propertyId,rev,claims,datatype,label,aliases,description):
		cur = self.connection.cursor()
		#curRev = self.getCurrentPropertyRevision(itemId)
		#if curRev == rev:
			#return None

		cur.execute("""
			INSERT INTO properties (id, rev, claims, datatype, label, aliases, description) VALUES(%s,%s,%s,%s,%s,%s,%s) \
				ON DUPLICATE KEY UPDATE
					rev = VALUES(rev),
					claims = VALUES(claims),
					label = VALUES(label),
					aliases = VALUES(aliases),
					description = VALUES(description)
			""", (propertyId,rev,claims,datatype,label,aliases,description))
		self.__addToCommitCount()
		#print "Number of rows updated:",  cur.rowcount

	# Get the current revision of a property in the properties table.
	# TODO Information on specific tables should be managed in the components that need them.
	def getCurrentPropertyRevision(self,propertyId):
		cur = self.connection.cursor()
		cur.execute("SELECT rev FROM properties WHERE id=%s", (propertyId))
		res = cur.fetchone()
		if res == None:
			return -1
		else:
			return res[0]

	# TODO Information on specific tables should be managed in the components that need them.
	def updateItemRevStatsData(self,itemId,rev,day,langinfo,propinfo,statNum,statRefNum,statQNum,labelNum,descNum,linkNum,aliasNum):
		cur = self.connection.cursor()

		cur.execute("""REPLACE INTO itemrevstats
				(id,rev,day,langinfo,propinfo,stat_num,stat_ref_num,stat_q_num,label_num,desc_num,link_num,alias_num)
				VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
			(itemId,rev,day,langinfo,propinfo,statNum,statRefNum,statQNum,labelNum,descNum,linkNum,aliasNum))
		self.__addToCommitCount()
		#print "Number of rows updated:",  cur.rowcount

	# TODO Information on specific tables should be managed in the components that need them.
	def getItemRevStatRevision(self,itemId,day):
		cur = self.connection.cursor()
		cur.execute("SELECT rev FROM itemrevstats WHERE id=%s AND day=%s", (itemId,day))
		res = cur.fetchone()
		if res == None:
			return -1
		else:
			return int(res[0])

	# TODO Information on specific tables should be managed in the components that need them.
	def updatePropertyRevStatsData(self,propertyId,rev,day,langinfo,labelNum,descNum,aliasNum):
		cur = self.connection.cursor()

		cur.execute("""
			INSERT INTO proprevstats (id,rev,day,langinfo,label_num,desc_num,alias_num) VALUES(%s,%s,%s,%s,%s,%s,%s) \
				ON DUPLICATE KEY UPDATE
					id = VALUES(id),
					day = VALUES(day),
					langinfo = VALUES(langinfo),
					label_num = VALUES(label_num),
					desc_num = VALUES(desc_num),
					alias_num = VALUES(alias_num)
			""", (propertyId,rev,day,langinfo,labelNum,descNum,aliasNum))
		self.__addToCommitCount()
		#print "Number of rows updated:",  cur.rowcount

	# TODO Information on specific tables should be managed in the components that need them.
	def getPropertyRevStatRevision(self,propertyId,day):
		cur = self.connection.cursor()
		cur.execute("SELECT rev FROM proprevstats WHERE id=%s AND day=%s", (propertyId,day))
		res = cur.fetchone()
		if res == None:
			return -1
		else:
			return int(res[0])

	# Increase the number of writing database queries since the
	# last commit. Every 1000 writes, commit is called to avoid
	# significant data loss on crashes.
	def __addToCommitCount(self):
		self.commitCount += 1
		if self.commitCount >= 1000:
			self.commit()
			self.commitCount = 0