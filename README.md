# SkinCares: Skincare Product Recommendation System

SkinCares is a machine learning system designed to recommend skincare products based on ingredient similarity, product attributes, and user preferences.

The system processes cosmetic product data, standardizes ingredient lists, and applies similarity-based models to generate personalized skincare recommendations.

---

## Project Overview

This project implements a full machine learning pipeline for skincare recommendation, including:

- Data preprocessing and ingredient standardization
- Feature engineering for product comparison
- Similarity-based recommendation models
- Evaluation and tuning of recommendation strategies

The system is designed with modular components to support experimentation, evaluation, and deployment.

---

## Repository Structure

```
SkinCares/
│
├── data/                # Raw and processed datasets
├── docs/                # Project documentation
├── examples/            # EDA and experimentation notebooks
├── miguellib/           # Core ML pipeline
│   ├── features/        # Feature engineering
│   ├── models/          # Recommendation models
│   ├── evaluation/      # Model evaluation
│   ├── tuning/          # Hyperparameter tuning
│   └── utils/           # Shared utilities
│
├── deployment/          # Deployment configuration
├── scripts/             # Pipeline execution scripts
├── tests/               # Unit tests
│
├── Dockerfile
├── docker-compose.yml
├── setup.py
└── README.md
```

---

## Installation

Clone the repository:

```bash
git clone https://github.com/cayetana-h/SkinCares.git
cd SkinCares
```

Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -e .
```

---

## Dependencies

Main dependencies include:

- Python 3.9+
- pandas
- numpy
- scikit-learn
- matplotlib
- seaborn
- jupyter
- pytest
- ruff (linting)

These dependencies are installed automatically through `setup.py`.

---

## Running the Pipeline

Example preprocessing workflow:

```bash
python scripts/preprocess_dataset.py
```

Example model training:

```bash
python scripts/train_model.py
```

---

## Development

Run tests:

```bash
pytest
```

Lint code:

```bash
ruff check .
```

---

## License

This project is licensed under the MIT License.