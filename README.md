# Plant Owl - Manufacturing Ontology

An ontology-based system for modeling manufacturing assets, events, and utilization states.

## Overview

Plant Owl provides a comprehensive OWL ontology for representing manufacturing data, with a focus on equipment utilization, downtime analysis, and process optimization. The ontology models plants, lines, equipment, and their relationships, as well as events that occur during production.

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/plant_owl.git
   cd plant_owl
   ```

2. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

## Usage

1. Prepare your CSV data file with manufacturing data.

2. Run the application:
   ```
   python main.py --input your_data.csv --output ontology_output.owl
   ```

3. Additional options:
   ```
   python main.py --help
   ```

## Project Structure

- `ontology/`: Ontology definition modules
  - `classes/`: Class definitions by domain
  - `properties/`: Property and relationship definitions
- `data/`: Data handling modules
  - `loaders.py`: Data loading functions
  - `processors.py`: Data preprocessing
  - `mappers.py`: Data to ontology mapping
- `utils/`: Utility functions
- `config/`: Configuration settings
- `queries/`: Reusable query functions

## Ontology Structure

The ontology is organized around these key concepts:

- Manufacturing Assets (Plant, Line, Equipment)
- Locations (Country, Strategic Location, Physical Area)
- Organizational Units (Divisions, Focus Factories)
- Process Context (Materials, Orders, Crews)
- Time-Related Entities (Time Intervals, Shifts)
- Event Records
- Utilization States and Reasons

## License

MIT License 