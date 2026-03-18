### What is EezyML

EezyML is the Vercel for deploying and monitoring AI models. It aims to simplify and optimize the process of deployment, monitoring, benchmarking, and tuning models by automating the management of optimized remote virtual machines.

### Getting Started

**Install the Python library:**

```bash
pip install eezyml
```

**Create a repository:**

```bash
eezy create my-eezy-project
cd my-eezy-project
```

Scaffolds a new eezy-ml project from the template repo into the target directory by cloning `/template`.

**Build the project:**

```bash
eezy init
```

Finds the nearest project containing `init.py` and runs it to download data and train the model.

**Start the server:**

```bash
eezy start
```

Starts the inference server, waits for `/health`, then runs `test.py`.

### Learn More

Detailed documentation is in progress. For more information about project structure, use AI agents to analyze `backend/src/utils.py` and `backend/README.md`.

