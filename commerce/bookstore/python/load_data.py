#
# Copyright (C) 2022 Vaticle
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#

import csv
from typedb.client import TypeDB, SessionType, TransactionType
import loaders
import config
import argparse

# Verbosity option implementation
parser = argparse.ArgumentParser(description='Loads data into TypeDB for the Bookstore example')
parser.add_argument("-v", "--verbose", "-d", "--debug", help='Increase output verbosity',
                    dest="verbose", action='store_true')
args = vars(parser.parse_args())

if args["verbose"]:  # if the argument was set
    print("High verbosity option turned on.")
    debug = True  # Shows verbose debug messages in the console output
else:
    debug = False  # No debug messages


def parse_data_to_dictionaries(input):  # input.file as string: the path to the data file
    if debug: print("Parsing of " + input["file"] + "started.")
    items = []  # prepare empty list
    with open(input("").file, encoding="UTF-8") as data:  # reads the input.file through a stream
        for row in csv.DictReader(data, delimiter=";", skipinitialspace=True):  # iterate through rows
            item = {key: value for key, value in row.items()}  # Creates an item. Keys are taken from the first row
            items.append(item)  # adds the dictionary to the list of items
    if debug: print("Parsing of " + input["file"] + " successful.")
    return items  # items as list of dictionaries: each item representing a data item from the file at input.file


def load_data_into_typedb(input, session):  # Requests generation of insert queries and sends queries to the TypeDB
    """
      :param input as class: has load method to build insert query. Object initiated with an item to insert
      :param session: an established connection to the TypeDB off of which a transaction will be created
    """
    items = parse_data_to_dictionaries(input)  # parses csv file (input.file) to create a list of dictionaries
    skip_count = 0  # counter of non-successful insert attempts
    for item in items:  # for each item dictionary in the list (former row in csv file)
        with session.transaction(TransactionType.WRITE) as transaction:  # creates a TypeDB transaction
            input_object = input(item)  # This is an object of input class initiated with an item as a parameter
            typeql_insert_query = input_object.load()  # This builds the corresponding TypeQL insert query from item
            if typeql_insert_query != "":
                if debug: print("Executing TypeQL Query: " + typeql_insert_query)
                transaction.query().insert(typeql_insert_query)  # runs the query
                transaction.commit()  # commits the transaction
                # todo: Add a transaction result check. Increase skip_cont if nothing was inserted
            else:
                if debug: print("Item parsing resulted in empty query statement. Skipping this item —", item)
                skip_count += 1
    print("Inserted " + str(len(items) - skip_count) + " out of " + str(len(items)) + " items from [ "
          + input_object.file + "] into TypeDB with", input.__name__)
    return  # END of load_data_into_typedb()


def load_data():  # Main data load function
    with TypeDB.core_client("localhost:1729") as client:
        with client.session(config.db, SessionType.DATA) as session:
            for input_type in loaders.Input_types_list:  # Iterating through the list of classes to import all data
                if debug: print("Loading from [" + input_type("").file + "] into TypeDB ...")
                load_data_into_typedb(input_type, session)  # Call to load data: session and import class as parameters
            print("\nData loading complete!")
    return


def has_existing_data():  # Checking whether the DB already has the schema and the data loaded
    with TypeDB.core_client("localhost:1729") as client:
        with client.session(config.db, SessionType.SCHEMA) as session:
            with session.transaction(TransactionType.READ) as transaction:
                try:
                    typeql_read_query = "match $b isa book, has ISBN $x; get $x; limit 3;"
                    transaction.query().match(typeql_read_query)
                    print("The DB contains the schema and loaded data already.")
                    return True  # Success means DB most likely already has the schema and the data loaded
                except:
                    return False  # Exception — we consider DB as empty (brand new, no schema, no data)


def load_schema():  # Loading schema
    with TypeDB.core_client("localhost:1729") as client:
        with client.session(config.db, SessionType.SCHEMA) as session:
            with open("../schema.tql", "r") as schema:  # Read the schema.tql file
                define_query = schema.read()
                with session.transaction(TransactionType.WRITE) as transaction:
                    try:
                        transaction.query().define(define_query)  # Execute query to load the schema
                        transaction.commit()  # Commit transaction
                        print("Loaded the " + config.db + " schema.")
                        return True  # Setup complete
                    except Exception as e:
                        print("Failed to load schema: " + str(e))
                        return False  # Setup failed


# This is the main body of this script
with TypeDB.core_client("localhost:1729") as client:
    if client.databases().contains(config.db):  # Check the DB existence
        print("Detected DB " + config.db + ". Connecting.")
        if not has_existing_data():  # Most likely the DB is empty and has no schema
            print("Attempting to load the schema and data.")
            if load_schema():  # Schema has been loaded
                load_data()  # Main data loading function
        else:  # The data check showed that we already have schema and some data in the DB
            print("To reload data we will delete the existing DB... Please confirm!")
            if input("Type in Delete to proceed with deletion: ") == "delete" or "Delete" or "DELETE":
                client.databases().get(config.db).delete()  # Deleting the DB
                print("Deleted DB " + config.db + ".")
                client.databases().create(config.db)  # Creating new (empty) DB
                print("DB " + config.db + " created. Applying schema...")
                if load_schema():  # Schema has been loaded
                    load_data()  # Main data loading function
            else:
                exit("Database was not deleted due to user choice. Exiting.")

    else:  # DB is non-existent
        print("DB " + config.db + " is absent. Trying to create.")
        client.databases().create(config.db)  # Creating the DB
        print("DB " + config.db + " created. Applying schema...")
        if load_schema():  # Schema has been loaded
            load_data()  # Main data loading function
