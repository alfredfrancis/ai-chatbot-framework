# Welcome Contributors! 👋

Thank you for your interest in contributing to AI Chatbot Framework! This document provides guidelines and steps for contributing to the project.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## How to Contribute

### Setting Up Development Environment

1. Fork the repository
2. Clone your fork:
```sh
git clone https://github.com/YOUR-USERNAME/ai-chatbot-framework.git
cd ai-chatbot-framework
```
3. Set up pre-commit hooks:
```sh
# Install pre-commit
pip install pre-commit

# Install the pre-commit hooks
pre-commit install
```

4. Set up development environment using Docker Compose:
```sh
docker-compose -f docker-compose.dev.yml up -d
```

The development server will be available at http://localhost:3000/


### Making Changes

1. Create a new branch:
```sh
git checkout -b feature/your-feature-name
```

2. Make your changes
3. Test your changes thoroughly
4. Commit your changes:
```sh
git add .
git commit -m "feat: describe your changes"
```

### Commit Message Guidelines

Follow conventional commits for your commit messages:
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation changes
- `test:` for test-related changes
- `refactor:` for code refactoring
- `style:` for code style changes
- `chore:` for maintenance tasks

### Pull Request Process

1. Push to your fork:
```sh
git push origin feature/your-feature-name
```

2. Create a Pull Request from your fork to the main repository
3. Ensure your PR description clearly describes the changes
4. Link any related issues
5. Wait for review and address any feedback

## Development Guidelines

### Project Structure
- `app/` - Backend Python/FastAPI application
- `frontend/` - Frontend NextJS application
- `helm/` - Helm charts for Kubernetes deployment
- `examples/` - Example implementations
- `docs/` - Project documentation

### Testing

Before submitting a PR:
1. Ensure all tests pass
2. Add tests for new features
3. Update documentation if needed

### Code Style

- Follow PEP 8 for Python code
- Use ESLint rules for JavaScript/React code
- Keep code modular and well-documented
- Add type hints in Python code where applicable

## Getting Help

- Join our [Gitter chat](https://gitter.im/ai-chatbot-framework/Lobby) for questions
- Create an issue for bugs or feature requests
- Check existing issues and PRs before creating new ones

## License

By contributing to AI Chatbot Framework, you agree that your contributions will be licensed under the project's license.
