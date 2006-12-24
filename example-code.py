#!/usr/bin/env python
#
# This is the example code. The file should run correctly as is.  coloursrc.py is run over this
# file and produces HTML escaped and coloured code, as well as output where indicated.

#@@BEGIN
import os, sys, time
import apsw

###
### Check we have the expected version of apsw and sqlite
###

#@@CAPTURE
print "Using APSW file",apsw.__file__                # from the extension module
print "   APSW version",apsw.apswversion()           # from the extension module
print " SQLite version",apsw.sqlitelibversion()      # from the sqlite library code
print " SQLite version",apsw.SQLITE_VERSION_NUMBER   # from the sqlite header file at compile time
#@@ENDCAPTURE

###
### Opening/creating database
###

if os.path.exists("dbfile"): os.remove("dbfile")
connection=apsw.Connection("dbfile")
cursor=connection.cursor()

###
### simple statement
###

cursor.execute("create table foo(x,y,z)")

###
### multiple statements
###

cursor.execute("insert into foo values(1,2,3); create table bar(a,b,c) ; insert into foo values(4, 'five', 6.0)")

###
### iterator
###

for x,y,z in cursor.execute("select x,y,z from foo"):
    print cursor.getdescription()  # shows column names and declared types
    print x,y,z

###        
### iterator - multiple statements
###

for m,n,o in cursor.execute("select x,y,z from foo ; select a,b,c from bar"):
    print m,n,o

###
### bindings - sequence
###

cursor.execute("insert into foo values(?,?,?)", (7, 'eight', False))
cursor.execute("insert into foo values(?,?,?1)", ('one', 'two'))  # nb sqlite does the numbers from 1

###
### bindings - dictionary
###

cursor.execute("insert into foo values(:alpha, :beta, :gamma)", {'alpha': 1, 'beta': 2, 'gamma': 'three'})

###
### <a name="example-exectrace">tracing execution</a> <!-@!@->
###

def mytrace(statement, bindings):
    "Called just before executing each statement"
    print "SQL:",statement
    if bindings:
        print "Bindings:",bindings
    return True  # if you return False then execution is aborted

#@@CAPTURE
cursor.setexectrace(mytrace)
cursor.execute("drop table bar ; create table bar(x,y,z); select * from foo where x=?", (3,))
#@@ENDCAPTURE

###
### <a name="example-rowtrace">tracing results</a> <!-@!@->
###

def rowtrace(*results):
    """Called with each row of results before they are handed off.  You can return None to
    cause the row to be skipped or a different set of values to return"""
    print "Row:",results
    return results

#@@CAPTURE
cursor.setrowtrace(rowtrace)
for row in cursor.execute("select x,y from foo where x>3"):
     pass
#@@ENDCAPTURE

# Clear tracers
cursor.setrowtrace(None)
cursor.setexectrace(None)

###
### executemany
###

# (This will work correctly with multiple statements, as well as statements that
# return data.  The second argument can be anything that is iterable.)
cursor.executemany("insert into foo (x) values(?)", ( [1], [2], [3] ) )

# You can also use it for statements that return data
for row in cursor.executemany("select * from foo where x=?", ( [1], [2], [3] ) ):
    print row

###
### defining your own functions
###

def ilove7(*args):
    "a scalar function"
    print "ilove7 got",args,"but I love 7"
    return 7

connection.createscalarfunction("seven", ilove7)

for row in cursor.execute("select seven(x,y) from foo"):
    print row

###
### aggregate functions are more complex
###

# here we return the longest item when represented as a string

def longeststep(context, *args):
    "are any of the arguments longer than our current candidate"
    for arg in args:
        if len( str(arg) ) > len( context['longest'] ):
            context['longest']=str(arg)

def longestfinal(context):
    "return the winner"
    return context['longest']

def longestfactory():
    """called for a new query.  The first item returned can be
    anything and is passed as the context to the step
    and final methods.  We use a dict."""
    return ( { 'longest': '' }, longeststep, longestfinal)

connection.createaggregatefunction("longest", longestfactory)

for row in cursor.execute("select longest(x) from foo"):
    print row

###
### Defining collations.  
###

# The default sorting mechanisms don't understand numbers at the end of strings
# so here we define a collation that does

cursor.execute("create table s(str)")
cursor.executemany("insert into s values(?)", 
                  ( ["file1"], ["file7"], ["file17"], ["file20"], ["file3"] ) )

#@@CAPTURE
for row in cursor.execute("select * from s order by str"):
    print row
#@@ENDCAPTURE

def strnumcollate(s1, s2):
    # return -1 if s1<s2, +1 if s1>s2 else 0
    
    # split values into two parts - the head and the numeric tail
    values=[s1, s2]
    for vn,v in enumerate(values):
        for i in range(len(v), 0, -1):
            if v[i-1] not in "01234567890":
                break
        try:
            v=( v[:i], int(v[i:]) )
        except ValueError:
            v=( v[:i], None )
        values[vn]=v
    # compare
    if values[0]<values[1]:
        return -1
    if values[0]>values[1]:
        return 1
    return 0

connection.createcollation("strnum", strnumcollate)

#@@CAPTURE
for row in cursor.execute("select * from s order by str collate strnum"):
    print row    
#@@ENDCAPTURE

###
### Authorizer (eg if you want to control what user supplied SQL can do)
###

def authorizer(operation, paramone, paramtwo, databasename, triggerorview):
    """Called when each operation is prepared.  We can return SQLITE_OK, SQLITE_DENY or
    SQLITE_IGNORE"""
    # find the operation name
    ign=["SQLITE_OK", "SQLITE_DENY", "SQLITE_IGNORE"]  # not operation names but have same values
    print "AUTHORIZER:",
    for i in dir(apsw):
        if getattr(apsw,i)==operation:
            print i,
            break
    print paramone, paramtwo, databasename, triggerorview
    if operation==apsw.SQLITE_CREATE_TABLE and paramone.startswith("private"):
        return apsw.SQLITE_DENY  # not allowed to create tables whose names start with private
    
    return apsw.SQLITE_OK  # always allow

connection.setauthorizer(authorizer)
#@@CAPTURE
cursor.execute("insert into s values('foo')")
cursor.execute("select str from s limit 1")
#@@ENDCAPTURE

# Cancel authorizer
connection.setauthorizer(None)

###
### progress handler (SQLite 3 experimental feature)
###

# something to give us large numbers of random numbers
import random
def randomintegers(howmany):
    for i in xrange(howmany):
        yield (random.randint(0,9999999999),)

# create a table with 500 random numbers
cursor.execute("begin ; create table bigone(x)")
cursor.executemany("insert into bigone values(?)", randomintegers(500))
cursor.execute("commit")

# display an ascii spinner
_phcount=0
_phspinner="|/-\\"
def progresshandler():
    global _phcount
    sys.stdout.write(_phspinner[_phcount%len(_phspinner)]+chr(8)) # chr(8) is backspace
    sys.stdout.flush()
    _phcount+=1
    time.sleep(0.1) # deliberate delay so we can see the spinner (SQLite is too fast otherwise!)
    return 0  # returning non-zero aborts

# register progresshandler every 20 instructions
connection.setprogresshandler(progresshandler, 20)

# see it in action - sorting 500 numbers to find the biggest takes a while
print "spinny thing -> ",
for i in cursor.execute("select max(x) from bigone"):
    print # newline
    print i # and the maximum number

###
### commit hook (SQLite3 experimental feature)
###

def mycommithook():
    print "in commit hook"
    hour=time.localtime()[3]
    if hour<8 or hour>17:
        print "no commits out of hours"
        return 1  # abort commits outside of 8am through 6pm
    print "commits okay at this time"
    return 0  # let commit go ahead

connection.setcommithook(mycommithook)
try:
    cursor.execute("begin; create table example(x,y,z); insert into example values (3,4,5) ; commit")
except apsw.ConstraintError:
    print "commit was not allowed"
    
###
### Cleanup
###

# We must close connections
del cursor
connection.close()
del connection

#@@END