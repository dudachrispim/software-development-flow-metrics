# Predictability and Bottlenecks in Open-Source Software Development Workflows: An Analysis Using Agile Metrics

This repository contains the replication package for the study:

> **Predictability and Bottlenecks in Open-Source Software Development Workflows: An Analysis Using Agile Metrics**

This study investigates the behavior of the software development flow in open-source projects, focusing on predictability and the identification of potential bottlenecks. The research adopts a quantitative approach based on metrics extracted from 3,233 public GitHub repositories. Flow metrics such as *cycle time*, *throughput*, and *release interval* were calculated, along with the coefficient of variation to analyze aspects of flow predictability. The results revealed significant differences in metric variability across repositories with different popularity levels and across stages of the development flow. Associations were also observed between delivery capacity and predictability indicators, particularly regarding *cycle time* variability.

The replication package includes the source code, processed datasets, and figures required to reproduce the analyses and results presented in the paper.

---

## Authors

- **Maria Eduarda Chrispim Santana** – Pontifícia Universidade Católica de Minas Gerais (PUC Minas)
- **Michelle Hanne Soares de Andrade** – Pontifícia Universidade Católica de Minas Gerais (PUC Minas)
- **Cleiton Silva Tavares** – Pontifícia Universidade Católica de Minas Gerais (PUC Minas)

---

## Requirements

Before reproducing the study, make sure the following requirements are installed:

- Python 3.11 or newer
- Git
- GitHub Personal Access Token (PAT)

---

## Reproduction Instructions

### 1. Clone the repository

```bash
git clone https://github.com/dudachrispim/software-development-flow-metrics.git

cd software-development-flow-metrics
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv
```

Windows

```bash
venv\Scripts\activate
```

Linux/macOS

```bash
source venv/bin/activate
```

### 3. Install the dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the GitHub API token

Create a GitHub Personal Access Token (PAT) with permission to access both the GitHub REST and GraphQL APIs. Configure the token as described in the source code before executing the data collection scripts.

### 5. Execute the workflow

The complete replication pipeline follows the sequence below.

#### Stage 1 – Repository Collection

- Repository Search
- Metadata Collection
- Repository Filtering

#### Stage 2 – Data Processing

- Detailed Artifact Collection
- Data Cleaning and Standardization
- Flow Metric Computation

#### Stage 3 – Data Analysis

- Exploratory Analysis
- Research Question 1 (RQ1): Flow Metric Variability Across Popularity Quartiles
- Research Question 2 (RQ2): Bottleneck Analysis
- Research Question 3 (RQ3): Relationship Between Predictability and Delivery Capability

All scripts are organized according to these stages in the project directories.

---

## Repository Structure

```text
software-development-flow-metrics/
│
├── data/
├── 01_coleta_repositorios/
├── 02_tratamento_dados/
├── 03_analise_dados/
├── requirements.txt
├── LICENSE
├── CITATION.cff
└── README.md
```

---

## Replication Package

The replication package contains:

- Source code used for repository collection;
- Data processing scripts;
- Flow metric computation scripts;
- Statistical analysis scripts;
- Processed datasets;
- Figures used in the paper.

Large intermediate files generated during repository collection were omitted from the online repository because they can be reproduced by executing the complete pipeline.

---

## Citation

If you use this replication package, please cite the associated publication and the software package described in `CITATION.cff`.

---

## License

This project is distributed under the **Creative Commons Attribution 4.0 International (CC BY 4.0)** License.
