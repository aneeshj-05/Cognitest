import type { ReactNode } from "react";
import { AuthProvider } from "./AuthContext";
import { ThemeProvider } from "./ThemeContext";
import { ProjectsProvider } from "./ProjectContext";
import { PermissionsProvider } from "./PermissionsContext";
import { MembersProvider } from "./MembersContext";
import { ToastProvider } from "@/components/ui/toast";

interface AppProvidersProps {
  children: ReactNode;
}

const AppProviders = ({ children }: AppProvidersProps) => (
  <ThemeProvider>
    <ToastProvider>
      <AuthProvider>
        <PermissionsProvider>
          <ProjectsProvider>
            <MembersProvider>{children}</MembersProvider>
          </ProjectsProvider>
        </PermissionsProvider>
      </AuthProvider>
    </ToastProvider>
  </ThemeProvider>
);

export default AppProviders;
