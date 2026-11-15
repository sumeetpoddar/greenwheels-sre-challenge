# AI Usage

AI tools were allowed and encouraged for this project, and I used them
throughout development. The application was created with substantial AI
assistance, while I directed the work, made decisions about the project, and
tested and debugged the result.

## Tools used

- **ChatGPT** — helped me get started with the application structure and
  implementation.
- **GitHub Copilot Agent in VS Code** — helped me investigate and debug the
  local Docker Compose setup and monitoring stack.

## Where AI accelerated the work

Before using AI for implementation, I created the project folders and initial
project files myself, including the README, `.env`, `.gitignore`, and
`.dockerignore`. I then used ChatGPT's coding assistance to build out the
application files under `app/`, the tests, and the Dockerfile. This gave me a
working starting point more quickly than writing each component from scratch.

AI was also useful while I added observability and monitoring. It helped me
iterate on configuration and code across the API, PostgreSQL, Prometheus, and
Grafana rather than treating those pieces as isolated tasks.

## Suggestions I rejected or corrected

During monitoring setup, ChatGPT got stuck repeatedly suggesting fixes around
port connectivity. The application was intermittently stopping or becoming
unreachable, and repeated variations of the same suggestion were not resolving
the underlying problem. I stopped that loop and switched to Copilot Agent,
which helped me debug the running services and work through the setup until the
stack was running.

More generally, when AI responses became random or distracted from the
specific failure, I narrowed the request, redirected the tool to the observed
symptoms, or stopped using that suggestion. I treated generated suggestions as
proposals, not as proof that a fix was correct.

## Where I kept human judgment

I made the project-scope and workflow decisions and used testing and direct
checks of the running services to confirm behavior. I did not treat a
plausible-looking answer or generated configuration as sufficient evidence
that the service worked. I also kept local secrets such as `.env` and any
future Slack webhook out of source control.

The scale-exercise architecture, on-call model, and incident guidance are
design/documentation proposals, not implemented infrastructure. I kept that
distinction explicit so readers would not mistake discussion of Kafka, ECS,
RDS, or Slack notifications for components already deployed in the application.
