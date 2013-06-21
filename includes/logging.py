#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys

# Write a message, followed by a newline
def log(message):
	print message

# Write a message without a newline
def logMore(message):
	sys.stdout.write(message)
	sys.stdout.flush()