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

### Docker Setup

Build the container from the repository root:

```bash
docker build -t eezy-ml .
```

The Docker build context ignores `.github`, `cli`, `template`, `thetemplate`,
`venv`, `.venv`, dependency folders, and local environment files.

Run the app with AWS credentials and any project configuration supplied through
environment variables:

```bash
docker run --rm \
  -p 8000:8000 \
  -e AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
  -e AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
  -e AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}" \
  -e PROJECTS_TABLE="${PROJECTS_TABLE:-eezy-ml-projects}" \
  eezy-ml
```

Open `http://localhost:8000`.

The container starts the backend API internally on port `3000` and the Next.js
client on port `8000`. Browser requests go through the client at `/api/*`, so
only port `8000` needs to be exposed. Do not bake credentials into the image;
pass them at runtime with `-e` or an `--env-file`.
