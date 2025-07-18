```javascript
module.exports = {
  root: true,
  env: {
    browser: true,
    es2021: true,
    node: true, // This is for the .cjs configuration file itself
  },
  extends: [
    'eslint:recommended',
    'plugin:react/recommended',
    'plugin:react-hooks/recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:prettier/recommended', // Enables eslint-plugin-prettier and eslint-config-prettier
  ],
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaFeatures: {
      jsx: true,
    },
    ecmaVersion: 'latest',
    sourceType: 'module',
    project: ['./tsconfig.json'], // Specifies the path to your tsconfig.json for type-aware rules
  },
  plugins: [
    'react',
    'react-hooks',
    '@typescript-eslint',
    'prettier',
  ],
  settings: {
    react: {
      version: 'detect', // Automatically detects the React version
    },
  },
  rules: {
    // Suppress warnings for missing React in scope for JSX in new React versions (React 17+)
    'react/react-in-jsx-scope': 'off',
    // Disable prop-types validation as TypeScript is used for type checking
    'react/prop-types': 'off',
    // Enforce consistent usage of type imports
    '@typescript-eslint/consistent-type-imports': 'warn',
    // Warn about usage of 'any' type
    '@typescript-eslint/no-explicit-any': 'warn',
    // Warn about unused variables, but allow variables prefixed with underscore (e.g., _unusedVar)
    '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    // Disable explicit module boundary types (often too strict for React components where types are inferred or from FC)
    '@typescript-eslint/explicit-module-boundary-types': 'off',
    // Allow non-null assertions (!)
    '@typescript-eslint/no-non-null-assertion': 'off',
    // Enforce Prettier formatting
    'prettier/prettier': [
      'error',
      {
        endOfLine: 'auto', // Normalize line endings across different OS
        // Add any other Prettier options you prefer here, e.g.:
        // semi: true,
        // singleQuote: true,
        // tabWidth: 2,
        // trailingComma: 'es5',
      },
    ],
    // Disallow console.log, but allow console.warn and console.error
    'no-console': ['warn', { allow: ['warn', 'error'] }],
    // No undeclared variables - often handled better by TypeScript itself
    'no-undef': 'off',
  },
  ignorePatterns: [
    'dist/',
    'build/',
    'node_modules/',
    'public/',
  ],
};
```