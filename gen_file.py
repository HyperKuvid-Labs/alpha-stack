GENERATABLE_FILENAMES = {
    'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml',
    'package.json', 'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml', 'tsconfig.json', 'jsconfig.json', 'next.config.js', 'next.config.mjs', 'babel.config.js', 'babel.config.json', 'postcss.config.js', 'tailwind.config.js', 'vite.config.js', 'vite.config.ts', 'webpack.config.js', 'webpack.config.ts', 'metro.config.js', 'metro.config.json',
    'requirements.txt', 'Pipfile', 'Pipfile.lock', 'pyproject.toml', 'setup.py', 'setup.cfg', 'manage.py', 'asgi.py', 'wsgi.py',
    'pom.xml', 'build.gradle', 'settings.gradle', 'gradlew', 'gradlew.bat', 'application.properties', 'application.yml', 'application.yaml',
    'composer.json', 'composer.lock', 'artisan', 'phpunit.xml',
    'Cargo.toml', 'Cargo.lock',
    'go.mod', 'go.sum', 'main.go',
    'Gemfile', 'Gemfile.lock', 'Rakefile',
    'mix.exs', 'mix.lock',
    'Program.cs', 'Startup.cs', 'appsettings.json',
    'Makefile', 'CMakeLists.txt',
    'Info.plist', 'Podfile', 'Podfile.lock', 'Cartfile', 'Cartfile.resolved',
    'build.gradle.kts', 'settings.gradle.kts', 'AndroidManifest.xml',
    'truffle-config.js', 'hardhat.config.js', 'foundry.toml', 'Anchor.toml',
    '.gitignore', '.gitattributes', '.env', '.env.example', '.editorconfig', '.prettierrc', '.prettierrc.js', '.prettierrc.json', '.eslintrc', '.eslintrc.js', '.eslintrc.json', '.eslintignore', '.stylelintrc', '.stylelintrc.json', '.lintstagedrc', '.huskyrc', '.github', '.github/workflows', '.gitlab-ci.yml', '.circleci/config.yml', 'Jenkinsfile', 'azure-pipelines.yml', '.travis.yml', '.appveyor.yml', 'netlify.toml', 'vercel.json',
    'README.md', 'README.rst', 'LICENSE', 'CONTRIBUTING.md', 'CHANGELOG.md', 'CODEOWNERS', 'SECURITY.md',
    'Procfile', 'Procfile.dev', 'Procfile.prod', 'now.json', 'firebase.json', 'manifest.json', 'robots.txt', 'sitemap.xml', 'favicon.ico', 'index.html', 'index.js', 'index.ts', 'index.jsx', 'index.tsx'
}
GENERATABLE_FILES = {
    '.py', '.pyi', #python, django, flask, fastapi
    '.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs', #for nodejs, mern, t3, react, next
    '.java', '.kt', '.kts', '.scala', '.groovy', #springboot, kotlin, scala
    '.php', '.phtml', #php, laravel
    '.rs', # rust
    '.go', #go
    '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.cs', '.m', '.mm', '.swift', #c, cpp, objective-c, swift
    '.rb', '.ex', '.exs', '.erl', #ruby, elixir, erlang
    '.html', '.htm', '.xhtml', '.xml', '.svg', '.xsl', #html, xml
    '.css', '.scss', '.sass', '.less', '.styl', #css
    '.json', '.yml', '.yaml', '.toml', '.ini', '.env', '.env.example', #json, yaml
    '.sh', '.bash', '.zsh', '.fish', '.bat', '.cmd', '.ps1', '.mk', '.make', '.cmake', '.gradle', '.mvn', #shell scripts, makefiles, gradle, maven
    '.md', '.rst', '.txt', '.adoc', '.asciidoc', #markdown, text files
    '.sql', '.sqlite', '.db', '.migration', #sql, database migrations
    '.mp3', '.wav', '.ogg', '.mp4', '.mov', '.webm', #audio, video
    '.dockerfile', '.tf', '.hcl', '.circleci', '.gitlab-ci.yml', '.jenkins', '.travis.yml', #docker, terraform, ci/cd
    '.sol', '.vy', '.cairo', '.move', '.clar', #solidity, vyper, cairo, move, clarity
    '.vue', '.svelte', '.dart', '.yaml', '.yml', '.json', '.tsx', '.jsx', #vue, svelte, dart
    '.lock', '.plist', '.conf', '.cfg', '.properties', '.pem', '.crt', '.csr', '.key', '.pub', '.crt', '.csr', #extra web shit files
}
