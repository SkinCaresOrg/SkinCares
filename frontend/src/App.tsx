import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Suspense, lazy } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  hasCompletedOnboardingForCurrentUser,
  isAuthenticated,
} from "./lib/session";

const Index = lazy(() => import("./pages/Index.tsx"));
const Onboarding = lazy(() => import("./pages/Onboarding.tsx"));
const Catalog = lazy(() => import("./pages/Catalog.tsx"));
const Recommendations = lazy(() => import("./pages/Recommendations.tsx"));
const Swiping = lazy(() => import("./pages/Swiping.tsx"));
const Profile = lazy(() => import("./pages/Profile.tsx"));
const NotFound = lazy(() => import("./pages/NotFound.tsx"));
const FloatingChat = lazy(() => import("./components/FloatingChat.tsx"));
const Login = lazy(() => import("./pages/Login.tsx"));
const Register = lazy(() => import("./pages/Register.tsx"));

const queryClient = new QueryClient();

const RequireAuth = ({ children }: { children: JSX.Element }) => {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  if (!hasCompletedOnboardingForCurrentUser()) {
    return <Navigate to="/onboarding" replace />;
  }
  return children;
};

const RequireOnboarding = ({ children }: { children: JSX.Element }) => {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  if (hasCompletedOnboardingForCurrentUser()) {
    return <Navigate to="/catalog" replace />;
  }
  return children;
};

const PublicOnly = ({ children }: { children: JSX.Element }) => {
  if (isAuthenticated()) {
    if (hasCompletedOnboardingForCurrentUser()) {
      return <Navigate to="/catalog" replace />;
    }
    return <Navigate to="/onboarding" replace />;
  }
  return children;
};

import { useLocation } from "react-router-dom";

const AppContent = () => {
  const location = useLocation();

  return (
    <>
      <Routes>
        <Route path="/" element={<PublicOnly><Index /></PublicOnly>} />
        <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
        <Route path="/register" element={<PublicOnly><Register /></PublicOnly>} />
        <Route path="/onboarding" element={<RequireOnboarding><Onboarding /></RequireOnboarding>} />
        <Route path="/catalog" element={<RequireAuth><Catalog /></RequireAuth>} />
        <Route path="/recommendations" element={<RequireAuth><Recommendations /></RequireAuth>} />
        <Route path="/swiping" element={<RequireAuth><Swiping /></RequireAuth>} />
        <Route path="/profile" element={<RequireAuth><Profile /></RequireAuth>} />
        <Route path="*" element={<NotFound />} />
      </Routes>

      {/* ✅ THIS is the only logic you need */}
      {!["/", "/login", "/register"].includes(location.pathname) && <FloatingChat />}
    </>
  );
};
const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Suspense fallback={null}>
          <FloatingChat />
          <Routes>
            <Route path="/" element={<PublicOnly><Index /></PublicOnly>} />
            <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
            <Route path="/register" element={<PublicOnly><Register /></PublicOnly>} />
            <Route path="/onboarding" element={<RequireOnboarding><Onboarding /></RequireOnboarding>} />
            <Route path="/catalog" element={<RequireAuth><Catalog /></RequireAuth>} />
            <Route path="/recommendations" element={<RequireAuth><Recommendations /></RequireAuth>} />
            <Route path="/swiping" element={<RequireAuth><Swiping /></RequireAuth>} />
            <Route path="/profile" element={<RequireAuth><Profile /></RequireAuth>} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Suspense>
      </BrowserRouter>

    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
