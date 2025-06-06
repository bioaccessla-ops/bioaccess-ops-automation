# Bioaccess Operations Automation (`bioaccess-ops-automation`)

This repository is the central monorepo for all internal software development projects aimed at automating operational processes at Bioaccess. The projects housed here are designed to increase efficiency, improve consistency, and enhance compliance across various business functions.

The primary goal of this initiative is to reduce manual overhead and strengthen our procedural integrity by creating robust, maintainable, and well-documented internal tools.

## Table of Contents

- [Scope of Projects](#scope-of-projects)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Development Workflow](#development-workflow)
- [Contributing](#contributing)
- [License](#license)

## Scope of Projects

The scope includes, but is not limited to:

* **Google Workspace Automation**: Scripts for automating tasks within the Google Workspace ecosystem (Google Sheets, Drive, etc.).
* **QA & Compliance Tools**: Tools to streamline quality assurance (QA) and regulatory compliance processes, such as document generation and control.
* **Admin & Data Management**: Utilities for managing system and data administration, like user permissions and access control.

## Repository Structure

This is a monorepo. All shared libraries and configurations are located at the root or in the `packages/` directory, while individual, deployable projects reside in the `projects/` directory.
```bash
/
├── .github/              # GitHub-specific configurations (e.g., Actions workflows, PR templates)
├── docs/                 # High-level, cross-project documentation (e.g., architecture)
├── packages/             # Shared, reusable code (e.g., common Apps Script libraries)
├── projects/             # Contains all individual, standalone projects
└── scripts/              # Repository-wide utility scripts (e.g., setup, lining)
```
Please refer to the documentation in each project's folder for specifics on that tool.

## Getting Started

Follow these instructions to set up the development environment on your local machine.

### Prerequisites

Ensure you have the following software installed:
* [Git](https://git-scm.com/)
* [Node.js](https://nodejs.org/) (LTS version recommended)
* [Clasp](https://github.com/google/clasp) (for Google Apps Script projects):
    ```bash
    npm install -g @google/clasp
    ```

### Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/jmoreno-bioaccessla/bioaccess-ops-automation.git](https://github.com/jmoreno-bioaccessla/bioaccess-ops-automation.git)
    cd bioaccess-ops-automation
    ```
2.  **Install dependencies:**
    *For a project that uses Node.js dependencies, navigate to its directory and run:*
    ```bash
    cd projects/your-project-name
    npm install
    ```

## Development Workflow

1.  Create a new feature branch from the `develop` branch following the naming conventions.
    ```bash
    git checkout develop
    git pull origin develop
    git checkout -b feature/your-feature-name
    ```
2.  Navigate to the specific project directory you will be working on within the `projects/` folder.
    ```bash
    cd projects/your-project-name
    ```
3.  Make your changes.
4.  Commit your changes and push the branch to the remote repository.
5.  Open a Pull Request (PR) on GitHub to merge your feature branch into `develop`.
6.  Assign a reviewer to your PR and ensure all checks pass before merging.

## Branching Strategy & Naming Conventions

To maintain a clean and predictable version history, this repository follows a simplified **Git Flow** branching model. All contributions must adhere to the following naming conventions.

### Primary Branches

* `main`: This branch contains production-ready, stable code. It is protected, and direct commits are not allowed. Changes are merged into `main` only through a release process from the `develop` branch.
* `develop`: This is the primary integration branch for all new work. All feature branches are created from `develop` and must be merged back into `develop` via a Pull Request.

### Branch Naming Best Practices

Every new branch should be created from the `develop` branch and must use a prefix to identify the nature of the work being done. This makes the purpose of each branch clear at a glance.

**Format:** `type/short-description`

#### Branch Types (`type`):

* **`feature/`**: For developing new features or functionality for any project.
    * *Example:* `feature/checklist-generator-ui`

* **`bugfix/`**: For fixing a non-urgent bug found in the `develop` branch.
    * *Example:* `bugfix/fix-permissions-script-logic`

* **`hotfix/`**: For critical, urgent fixes that must be applied to `main`. This is the only branch created directly from `main`.
    * *Example:* `hotfix/critical-security-patch`

* **`docs/`**: For adding or updating documentation only.
    * *Example:* `docs/add-contributing-guide`

* **`chore/`**: For repository maintenance tasks that do not affect production code.
    * *Example:* `chore/update-clasp-version`

## Contributing

Contributions are welcome! Please read our `CONTRIBUTING.md` guide (link to be added) to understand our coding standards and the full pull request process.