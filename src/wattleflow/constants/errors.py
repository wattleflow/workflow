# Module Name: core/constants/errors.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains error constants.


# Authentication
ERROR_AUTHENTICATION = "Authentication error: {}"

# Classification
ERROR_CLASSIFICATION = "Classification error: {}"

# Files, paths
ERROR_PATH_NOT_FOUND = "Path not found: {}"
ERROR_READING_FILE = "Error reading file: {}"
ERROR_READING_URI = "Error reading uri: {}"
ERROR_WRITING_FILE = "Error writing file: {}"

# Classes, types etc. handling
ERROR_CREATION_FAILED = "Failed to create {}: {}"
ERROR_HANDLING_FILE = "Error handling file: {}"
ERROR_CLASS_EXCEPTION_CAUGHT = "Class {} caught {} exception: {}"
ERROR_INCORRECT_TYPE = "Incorrect type found: {}"
ERROR_KWARGS_ERROR = "Key {} kwargs exception: {}"

# Keys types and values
ERROR_MISSING_ATTRIBUTE = "missing: [{}]"
ERROR_MANDATORY_ATTRIBUTE = "mandatory: [{}]"
ERROR_NOT_FOUND = "{} not found in {}"
ERROR_NOT_IMPLEMENTED = "Not implemented: {}"
ERROR_RESTRICTED_NAME = "Restricted name: {}"
ERROR_UNEXPECTED_TYPE = "{}.{}: Unexpected type found [{}] expected [{}]"

# Server Connections
ERROR_SERVER_CONNECTION = "Connecting to server: {}"
ERROR_SERVER_RESPONSE = "Error fetching server response: {}"
ERROR_NOT_INITIALISED = "Connection not initialised"

# Strategies
ERROR_STRATEGY = "Strategy error: {}"
ERROR_MISSING_STRATEGY_CREATE = "Missing create strategy: {}"
ERROR_MISSING_STRATEGY_READ = "Missing read strategy: {}"
ERROR_MISSING_STRATEGY_WRITE = "Missing write strategy: {}"

# Iteration
ERROR_ITERRRATION = "Iterration error at line [{}]: {}"

# Processing
ERROR_PROCESSING = "Processing error: {}"
ERROR_PROCESSING_TASK = "Error processing task: {}"
