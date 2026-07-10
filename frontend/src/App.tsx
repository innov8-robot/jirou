import { useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import LoginPage from '@/pages/LoginPage';
import RegisterPage from '@/pages/RegisterPage';
import ProjectsPage from '@/pages/ProjectsPage';
import ProjectOverviewPage from '@/pages/ProjectOverviewPage';
import ProjectSettingsPage from '@/pages/ProjectSettingsPage';
import IssuesPage from '@/pages/IssuesPage';
import IssueDetailPage from '@/pages/IssueDetailPage';
import BoardPage from '@/pages/BoardPage';
import BacklogPage from '@/pages/BacklogPage';
import TimelinePage from '@/pages/TimelinePage';
import DocumentsPage from '@/pages/DocumentsPage';
import GlobalDocsPage from '@/pages/GlobalDocsPage';
import ChatPage from '@/pages/ChatPage';
import ReportsPage from '@/pages/ReportsPage';
import MyWorkPage from '@/pages/MyWorkPage';
import ProfilePage from '@/pages/ProfilePage';
import AdminUsersPage from '@/pages/AdminUsersPage';
import StyleguidePage from '@/pages/StyleguidePage';
import { ProjectLayout } from '@/features/projects/ProjectLayout';
import { AppLayout } from '@/components/layout/AppLayout';
import { CreateIssueModal } from '@/components/CreateIssueModal';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { Toaster } from '@/components/ui/sonner';
import { ShortcutsHelp } from '@/components/ShortcutsHelp';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';
import { useAuthStore } from '@/stores/authStore';

export default function App() {
  const [helpOpen, setHelpOpen] = useState(false);
  // Raccourcis globaux : c (créer), / (rechercher), ? (aide) — JIR-73.
  useKeyboardShortcuts(() => setHelpOpen(true));

  // Au démarrage : valide le token persisté via /me (JIR-14).
  useEffect(() => {
    void useAuthStore.getState().hydrate();
  }, []);

  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/" element={<Navigate to="/projects" replace />} />

        {/* Public routes — no app shell. */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Authenticated routes — session required, wrapped in the app shell. */}
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/my-work" element={<MyWorkPage />} />
            <Route path="/docs" element={<GlobalDocsPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route element={<ProtectedRoute roles={['admin']} />}>
              <Route path="/reports" element={<ReportsPage />} />
            </Route>
            <Route path="/projects" element={<ProjectsPage />} />
            <Route path="/projects/:projectId" element={<ProjectLayout />}>
              <Route index element={<ProjectOverviewPage />} />
              <Route path="issues" element={<IssuesPage />} />
              <Route path="issues/:issueKey" element={<IssueDetailPage />} />
              <Route path="board" element={<BoardPage />} />
              <Route path="backlog" element={<BacklogPage />} />
              <Route path="timeline" element={<TimelinePage />} />
              <Route path="docs" element={<DocumentsPage />} />
              <Route path="settings" element={<ProjectSettingsPage />} />
            </Route>
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/styleguide" element={<StyleguidePage />} />

            {/* Admin-only area. */}
            <Route element={<ProtectedRoute roles={['admin']} />}>
              <Route path="/admin/users" element={<AdminUsersPage />} />
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Routes>

      {/* App-wide singletons: toast host + global quick-create modal. */}
      <Toaster />
      <CreateIssueModal />
      <ShortcutsHelp open={helpOpen} onOpenChange={setHelpOpen} />
    </ErrorBoundary>
  );
}
