import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import LoginPage from "./page";

const mockLogin = vi.fn();
const mockReplace = vi.fn();
let mockUser: {
  userId: string;
  email: string;
  role: string;
  tenantId: string;
  tenantSlug: null;
} | null = null;

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: mockUser,
    login: mockLogin,
    getAccessToken: () => null,
    setAccessToken: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
}));

vi.mock("@/components/ui/spinner", () => ({
  Spinner: () => <span data-testid="spinner" />,
}));

describe("LoginPage", () => {
  beforeEach(() => {
    mockUser = null;
    vi.clearAllMocks();
  });

  it("renders email and password fields and submit button", () => {
    render(<LoginPage />);
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("successful login calls useAuth().login and redirects to /dashboard", async () => {
    mockLogin.mockResolvedValue(undefined);
    render(<LoginPage />);

    await userEvent.type(screen.getByLabelText("Email"), "admin@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "correctpass");
    await userEvent.click(screen.getByRole("button", { name: /sign in →/i }));

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith("admin@example.com", "correctpass");
      expect(mockReplace).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("failed login shows error message, stays on page", async () => {
    mockLogin.mockRejectedValue(new Error("Invalid credentials"));
    render(<LoginPage />);

    await userEvent.type(screen.getByLabelText("Email"), "bad@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /sign in →/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Invalid credentials");
    });
    expect(mockReplace).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Password")).toHaveValue("wrong");
  });

  it("button is disabled and shows spinner while request is in-flight", async () => {
    let resolveLogin!: () => void;
    mockLogin.mockReturnValue(
      new Promise<void>((resolve) => {
        resolveLogin = resolve;
      }),
    );
    render(<LoginPage />);

    await userEvent.type(screen.getByLabelText("Email"), "test@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "password");
    fireEvent.click(screen.getByRole("button", { name: /sign in →/i }));

    await waitFor(() => {
      expect(screen.getByRole("button")).toBeDisabled();
      expect(screen.getByTestId("spinner")).toBeInTheDocument();
    });

    resolveLogin();
  });

  it("already-authenticated user is redirected to /dashboard", async () => {
    mockUser = {
      userId: "1",
      email: "admin@example.com",
      role: "system_admin",
      tenantId: "t-1",
      tenantSlug: null,
    };
    render(<LoginPage />);
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/dashboard");
    });
  });
});

describe("LoginPage — demo chips", () => {
  beforeEach(() => {
    mockUser = null;
    vi.clearAllMocks();
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "true");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("shows four role chips when DEMO_MODE is true", () => {
    render(<LoginPage />);
    expect(screen.getByRole("button", { name: "system_admin" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "tenant_admin" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "annotator" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "business_user" })).toBeInTheDocument();
  });

  it("clicking a chip fills email and password fields", async () => {
    render(<LoginPage />);
    await userEvent.click(screen.getByRole("button", { name: "tenant_admin" }));
    await waitFor(() => {
      expect(screen.getByLabelText("Email")).toHaveValue("tenant_admin@acme.dev");
      expect(screen.getByLabelText("Password")).toHaveValue("Admin123!");
    });
  });

  it("demo chips are absent when DEMO_MODE is not true", () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_MODE", "false");
    render(<LoginPage />);
    expect(screen.queryByRole("button", { name: "system_admin" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "tenant_admin" })).not.toBeInTheDocument();
  });
});
