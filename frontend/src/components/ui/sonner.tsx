import { Toaster as SonnerToaster } from "sonner";

/** App-wide toast host. Styled to match the indigo theme. */
export function Toaster() {
  return (
    <SonnerToaster
      position="top-center"
      richColors
      closeButton
      toastOptions={{
        classNames: {
          toast:
            "rounded-xl border border-border bg-background text-foreground shadow-lg",
        },
      }}
    />
  );
}
