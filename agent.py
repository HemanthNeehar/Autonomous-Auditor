# This file acts as the entry point for the ADK deployment tool
# It maps your custom agent variable and location to the default expected by the CLI

import sys
import os

# Add the current directory to sys.path so the 'agents' module can be found
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agents.agent import auditor_agent as root_agent
