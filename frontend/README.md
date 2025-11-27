# Project Management Frontend

React + TypeScript frontend for the Project Management System.

## Technology Stack

- **React 19** with TypeScript (strict mode)
- **Vite** - Fast build tool and dev server
- **Axios** - HTTP client for API calls
- **ESLint** - Code linting

## Getting Started

### Install Dependencies

```bash
npm install
```

### Development Server

```bash
npm run dev
```

The frontend will start on port 3000 (or 3001 if 3000 is in use).

**Note**: The backend must be running on port 8000 for the frontend to connect.

### Start Backend

From the project root:

```bash
uv run uvicorn project_management_crud_example.app:app --reload --port 8000
```

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run lint` - Run ESLint
- `npm run typecheck` - Run TypeScript type checking
- `npm run preview` - Preview production build

## Project Structure

```
frontend/
├── src/
│   ├── App.tsx              # Main application component
│   ├── main.tsx             # Entry point
│   ├── index.css            # Global styles
│   └── services/
│       └── api.ts           # API client service
├── index.html               # HTML template
├── vite.config.ts           # Vite configuration
├── tsconfig.json            # TypeScript configuration
└── package.json             # Dependencies and scripts
```

## API Integration

The frontend connects to the backend API at `http://localhost:8000`.

Current features:
- Health check connection status
- Displays connection success/failure

## Development Notes

- The app uses strict TypeScript configuration
- CORS is already configured on the backend
- All API calls go through the centralized API client in `services/api.ts`
