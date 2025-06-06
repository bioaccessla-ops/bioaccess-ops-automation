# Bioaccess Operations Automation (`bioaccess-ops-automation`)

This repository is the central monorepo for all internal software development projects aimed at automating operational processes at Bioaccess. The projects housed here are designed to increase efficiency, improve consistency, and enhance compliance across various business functions.

The primary goal of this initiative is to reduce manual overhead and strengthen our procedural integrity by creating robust, maintainable, and well-documented internal tools.

## Table of Contents

- [Scope of Projects](#scope-of-projects)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Setting Up Signed Commits](#setting-up-signed-commits)
  - [Option 1: Using a GPG Key](#option-1-using-a-gpg-key-traditional-method)
  - [Option 2: Using an SSH Key](#option-2-using-an-ssh-key-simpler-if-you-already-use-ssh-for-git)
- [Development Workflow](#development-workflow)
- [Branching Strategy & Naming Conventions](#branching-strategy--naming-conventions)
- [Contributing](#contributing)
- [License](#license)

## Scope of Projects

The scope includes, but is not limited to:

* **Google Workspace Automation**: Scripts for automating tasks within the Google Workspace ecosystem (Google Sheets, Drive, etc.).
* **QA & Compliance Tools**: Tools to streamline quality assurance (QA) and regulatory compliance processes, such as document generation and control.
* **Admin & Data Management**: Utilities for managing system and data administration, like user permissions and access control.

## Repository Structure

This is a monorepo. All shared libraries and configurations are located at the root or in the `packages/` directory, while individual, deployable projects reside in the `projects/` directory.

```
/
├── .github/              # GitHub-specific configurations (e.g., Actions workflows, PR templates)
├── docs/                 # High-level, cross-project documentation (e.g., architecture)
├── packages/             # Shared, reusable code (e.g., common Apps Script libraries)
├── projects/             # Contains all individual, standalone projects
└── scripts/              # Repository-wide utility scripts (e.g., setup, linting)
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

## Setting Up Signed Commits

To ensure the highest level of security and traceability, this repository requires that all commits be signed. A signed commit cryptographically verifies the identity of the person who made the change. This is a small one-time setup for each developer, but the security and traceability benefits are immense.

You can sign commits using either a GPG key or an SSH key. Follow the instructions for the method you prefer.

### Option 1: Using a GPG Key (Traditional Method)

**1. Check for Existing GPG Keys**
   First, check if you already have a key on your machine:
   ```bash
   gpg --list-secret-keys --keyid-format=long
   ```

**2. Generate a New GPG Key**
   If the command above does not return any keys, generate a new one:
   ```bash
   gpg --full-generate-key
   ```
   Follow the prompts on screen. It's recommended to use the default `RSA and RSA`, a key size of `4096`, and an appropriate expiration date. **Crucially, the email address you provide must be a verified email on your GitHub account.**

**3. Add Your GPG Key to GitHub**
   * First, get the ID of the key you want to use (from the `sec` line in the list command output):
       ```bash
       gpg --list-secret-keys --keyid-format=long
       ```
   * Export the public key using that ID:
       ```bash
       gpg --armor --export YOUR_GPG_KEY_ID
       ```
   * Copy the entire output block, including the `-----BEGIN...` and `-----END...` lines.
   * Navigate to your GitHub **Settings** > **SSH and GPG keys**, click **New GPG key**, and paste the key you copied.

**4. Configure Git to Use Your Key**
   * Tell Git which key to use for signing:
       ```bash
       git config --global user.signingkey YOUR_GPG_KEY_ID
       ```
   * To avoid having to use the `-S` flag for every commit, you can configure Git to sign all commits by default:
       ```bash
       git config --global commit.gpgsign true
       ```

### Option 2: Using an SSH Key (Simpler if you already use SSH for Git)

If you already use an SSH key to authenticate with GitHub, you can configure Git to use it for signing as well.

**1. Configure Git to Use SSH for Signing**
   * Tell Git to use the SSH format for GPG signing:
       ```bash
       git config --global gpg.format ssh
       ```
   * Tell Git which public SSH key to use for signing. You must provide the full path to your **public** key file:
       ```bash
       # Replace with the actual path to your public key file (e.g., id_ed25519.pub)
       git config --global user.signingkey /Users/your-username/.ssh/id_rsa.pub
       ```
   * Configure Git to sign all commits automatically:
       ```bash
       git config --global commit.gpgsign true
       ```

### How to Verify
After completing the setup, make a new commit in any repository. When you push this commit to GitHub, you should now see a green **"Verified"** badge next to it.

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
    * *Example:* `chore/update-clasp-version

