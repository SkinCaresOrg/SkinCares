import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import Index from "./pages/Index.tsx";
import Onboarding from "./pages/Onboarding.tsx";
import Catalog from "./pages/Catalog.tsx";
import Recommendations from "./pages/Recommendations.tsx";
import Swiping from "./pages/Swiping.tsx";
import Profile from "./pages/Profile.tsx";
import NotFound from "./pages/NotFound.tsx";
import FloatingChat from "./components/FloatingChat.tsx";

import Login from "./pages/Login.tsx";
import Register from "./pages/Register.tsx";
import {
  hasCompletedOnboardingForCurrentUser,
  isAuthenticated,
} from "./lib/session";

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
      return <Navigate to="/swiping" replace />;
    }
    return <Navigate to="/onboarding" replace />;
  }
  return children;
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <FloatingChat />
      <BrowserRouter>
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
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
