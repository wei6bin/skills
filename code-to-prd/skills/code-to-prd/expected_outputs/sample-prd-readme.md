# My App — Product Requirements Document

## System Overview

My App is a user management platform for internal teams. It provides CRUD
operations for users, a dashboard with key metrics, and system settings. Built
with Next.js 14 (App Router) and Tailwind CSS.

## Module Overview

| Module          | Pages                  | Core Functionality          |
| --------------- | ---------------------- | --------------------------- |
| Dashboard       | Dashboard              | Key metrics, activity feed  |
| User Management | User list, User detail | CRUD users, role assignment |
| Settings        | Settings               | System configuration        |

## Page Inventory

| #   | Page Name   | Route      | Module    | Doc Link                        |
| --- | ----------- | ---------- | --------- | ------------------------------- |
| 101 | Home        | /          | —         | [→](./pages/101-home.md)        |
| 201 | Dashboard   | /dashboard | Dashboard | [→](./pages/201-dashboard.md)   |
| 301 | User List   | /users     | User Mgmt | [→](./pages/301-user-list.md)   |
| 302 | User Detail | /users/:id | User Mgmt | [→](./pages/302-user-detail.md) |
| 401 | Settings    | /settings  | Settings  | [→](./pages/401-settings.md)    |

## Page Numbering

Pages are numbered in blocks of 100 per module. A new page takes the next free
number in its module's block; a new module takes the next free block.

| Block | Module          | First page                          |
| ----- | --------------- | ----------------------------------- |
| 1xx   | Home            | [101](./pages/101-home.md)          |
| 2xx   | Dashboard       | [201](./pages/201-dashboard.md)     |
| 3xx   | User Management | [301](./pages/301-user-list.md)     |
| 4xx   | Settings        | [401](./pages/401-settings.md)      |

## API Inventory

| #   | Method | Path                 | Status     | Notes             |
| --- | ------ | -------------------- | ---------- | ----------------- |
| 1   | GET    | /api/users           | Integrated | Paginated list    |
| 2   | POST   | /api/users           | Integrated | Create user       |
| 3   | GET    | /api/users/:id       | Integrated | User detail       |
| 4   | PUT    | /api/users/:id       | Integrated | Update user       |
| 5   | GET    | /api/dashboard/stats | Mock       | Dashboard metrics |

## Global Notes

### Permission Model

Role-based access: ADMIN (full access), MANAGER (read + edit), USER (read-only).

### Common Interaction Patterns

- All delete operations require confirmation modal
- Lists default to `created_at` descending, 20 items per page
- Form validation shows inline errors below each field
