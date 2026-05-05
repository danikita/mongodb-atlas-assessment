# mongodb-atlas-assessment
This repository contains code that performs an assessment of a MongoDB Atlas environment, evaluating the usage of native MongoDB features and core database characteristics.

## Requirements

- Operating System:
  - Amazon Linux (2 or 2023) **or**
  - Ubuntu (20.04+)

- Python:
  - Python 3.x
  - pip3 (Python package manager)

- Python Libraries:
  - pymongo
  - requests

- Node.js:
  - Node.js 20.x
  - npm

- MongoDB Tooling:
  - MongoDB Realm CLI (`mongodb-realm-cli`)
  - MongoDB Shell (`mongosh`)

- Additional Tools:
  - curl (used for installing Node.js)


## Installation

Install the required dependency:

```bash
chmod +x setup.sh
./setup.sh
```

## Step 1 - Database Triggers Assessment

The script `export_triggers.py` uses the **MongoDB Realm CLI** to analyze whether the MongoDB Atlas cluster makes use of **Database Triggers**.

### How it works

- The script invokes the MongoDB Realm CLI to fetch application and trigger metadata.
- It checks if Database Triggers are configured and enabled in the MongoDB Atlas environment.
- If Database Triggers are found, the script exports their definitions.
- During execution, the user is prompted to choose an output directory.
- The results are then generated in a structured folder hierarchy inside the selected directory, organizing the exported triggers for easy review and analysis.

### Execution

Run the script using Python 3:

```bash
python3 export_triggers.py
```

## Step 2 – Assessment Generator

The script `assessment_generator.py` is responsible for generating the final MongoDB Atlas environment assessment.

### What it does

- Performs a full scan of **all projects within a MongoDB Atlas organization**.
- Collects configuration and usage data from each project and its clusters.
- Correlates cluster information with Database Trigger data exported in Step 1.

As output, the script generates:

- `atlas_auto_assessment.json`
- `atlas_auto_assessment.xlsx`

### Execution

Run the script using Python 3:

```bash
python3 assessment_generator.py
```

