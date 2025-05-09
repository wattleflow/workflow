# Module Name: core/constants/enum.py
# Author: (wattleflow@outlook.com)
# Copyright: (c) 2022-2024 WattleFlow
# License: Apache 2 Licence
# Description: This modul contains wattleflow enumerated types.

from enum import Enum


# Classification
class Classification(Enum):
    UNCLASSIFIED = "UNCLASSIFIED"
    OFFICIAL = "OFFICIAL"
    PROTECTED = "PROTECTED"
    SECRET = "SECRET"
    TOP_SECRET = "TOP_SECRET"
    UNDEFINED = ""


# Classification DLM
class ClassificationDLM(Enum):
    CABINET = "Cabinet"
    LEGAL_PREVILEGE = "Legal Privilege"
    SENSITIVE = "Sensitive"
    UNCLASSIFIED = "UNCLASSIFIED"
    UNDEFINED = ""


# Events
class Event(Enum):
    Idle = "Idle"
    Accessing = "Accessing"
    Added = "Added"
    Adding = "Adding"
    Audit = "Audit"
    Authenticate = "Authenticate"
    Authentication = "Authentication"
    Authenticating = "Authenticating"
    Authenticated = "Authenticated"
    Check = "Check"
    Checking = "Checking"
    Classification = "Classification"
    Classifying = "Classifying"
    Completed = "Completed"
    Constructor = "Constructor"
    Connect = "Connect"
    Connection = "Connection"
    Connecting = "Connecting"
    Connected = "Connected"
    Configuring = "Configuring"
    Configuration = "Configuration"
    Create = "Create"
    Creating = "Creating"
    Created = "Created"
    DebugLog = "Debug log"
    Debug = "Debug"
    Debuging = "Debuging"
    Delete = "Delete"
    Deleting = "Deleting"
    Destructor = "Destructor"
    Disconnect = "Disconnect"
    Disconnecting = "Disconnecting"
    Disconnected = "Disconnected"
    Download = "Download"
    Downloading = "Downloading"
    Downloaded = "Downloaded"
    Exist = "Exist"
    Exists = "Exists"
    Existing = "Existing"
    Exporting = "Exporting"
    Exported = "Exported"
    Executing = "Executing"
    Executed = "Executed"
    Error = "Error"
    ErrorSource = "Error source"
    Exception = "Exception"
    ErrorDetails = "Error details"
    Failed = "Failed"
    Get = "Get"
    Getting = "Getting"
    Initialising = "Initialising"
    Initialised = "Initialised"
    Iterating = "Iterating"
    Iteration = "Iteration"
    Log = "Log"
    Missing = "Missing"
    OrchestrationCompleted = "Orchestration completed"
    OrchestrationStarted = "Orchestration started"
    OrchestrationStopped = "Orchestration stopped"
    PipelineProces = "Pipeline process"
    Processed = "Processed"
    Processing = "Processing"
    ProcessingTask = "Processing task"
    Push = "Push"
    Pushing = "Pushing"
    Pushed = "Pushed"
    Reading = "Reading"
    Registered = "Registered"
    Registering = "Registering"
    Rendered = "Rendered"
    Rendering = "Rendering"
    Retrieve = "Retrieve"
    Retrieved = "Retrieved"
    Retrieving = "Retrieving"
    Started = "Started"
    Storing = "Storing"
    Stored = "Stored"
    Stopped = "Stopped"
    Subscribing = "Subscribing"
    TaskCompleted = "Task completed"
    Updated = "Updated"
    Updating = "Updating"
    Upload = "Upload"
    Uploading = "Uploading"
    Uploaded = "Uploaded"
    Write = "Write"
    Writting = "Writting"
    Written = "Written"


class Operation(Enum):
    Start = 1
    Stop = 0
    Connect = 3
    Disconnect = 4


# Action
class PipelineAction(Enum):
    CONNECT = "5bb4dc6f-47d4-c040-9844-a72464984b14"
    DISCONNECT = "6ab06dcf-aa51-790d-d7c9-6d52d3be8ae0"
    EXTRACT = "40803834-9041-9ffc-e52d-9a66c5fac20b"
    TRANSFORM = "00c9bf50-c91c-2d07-e985-1cd554537678"
    LOAD = "d438686e-54df-812d-53df-373e2ca6a962"
    SCHEDULE = "5a40b6fd-b0ca-155a-3050-4aa62f93a7c5"
    RELEASE_DATE = "20241030"
    VERSION = "0.0.0.1"


# Supported pipline types
class PipelineType(Enum):
    ASYNC_PIPELINE = "ASYNC_PIPELINE"  # "2a6737f3-93f5-950b-832c-cfd78829c69c"
    BASE_PIPELINE = "BASE_PIPELINE"  # "1916fa2b-7d51-c4f2-e28e-61e8fc4c386d"
    CONFIGURATION_PIPELINE = "CONFIGURATION_PIPELINE"
    CONNECTION_PIPELINE = (
        "CONNECTION_PIPELINE"  # "c3535bf0-a399-8fce-a609-92c0b072fe52"
    )
    EXTRACTION_PIPELINE = (
        "EXTRACTION_PIPELINE"  # "df1999d3-28f7-a17d-764e-8d0eb9c01dca"
    )
    LOAD_PIPELINE = "LOAD_PIPELINE"  # "85593db0-62ba-e953-b9da-aa1860025880"
    # FEATURE_PIPELINE = "966fc1db-7e8c-62f2-178c-b3c74d8ba70b"
    STRATEGY_PIPELINE = "STRATEGY_PIPELINE"
    TRANSFORMATION_PIPELINE = (
        "TRANSFORMATION_PIPELINE"  # "fa7a9304-7b92-bf00-2374-a899ee239dfe"
    )
    RELEASE_DATE = "20241030"
    VERSION = "0.0.0.1"
