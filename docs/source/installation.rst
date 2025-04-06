Installation
============

Requirements
-----------
- Python 3.8 or higher
- pip (Python package installer)

Installation Steps
----------------
1. Clone the repository:

   .. code-block:: bash

      git clone https://github.com/yourusername/opera_onto.git
      cd opera_onto

2. Create and activate a virtual environment (recommended):

   .. code-block:: bash

      python -m venv venv
      source venv/bin/activate  # On Windows, use: venv\Scripts\activate

3. Install the package:

   .. code-block:: bash

      pip install -e .

Dependencies
-----------
The package will automatically install all required dependencies. Key dependencies include:

- owlready2
- pandas
- numpy
- logging

Optional Dependencies
-------------------
For development and documentation:

.. code-block:: bash

   pip install -e ".[dev]" 