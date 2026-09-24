using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;

internal static class ArdorPressureTestLauncher
{
    private const string SiteUrl = "https://84-247-130-242.sslip.io";

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int MessageBox(IntPtr handle, string text, string caption, uint type);

    [STAThread]
    private static void Main()
    {
        try
        {
            string browser = FindAppBrowser();
            if (browser != null)
            {
                Process.Start(new ProcessStartInfo
                {
                    FileName = browser,
                    Arguments = "--app=\"" + SiteUrl + "\" --start-maximized",
                    UseShellExecute = true
                });
                return;
            }

            Process.Start(new ProcessStartInfo
            {
                FileName = SiteUrl,
                UseShellExecute = true
            });
        }
        catch
        {
            MessageBox(
                IntPtr.Zero,
                "Не удалось открыть ARDOR Pressure Test. Проверьте подключение к интернету и наличие Microsoft Edge или Google Chrome.",
                "ARDOR Pressure Test",
                0x10
            );
        }
    }

    private static string FindAppBrowser()
    {
        string[] candidates =
        {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Microsoft", "Edge", "Application", "msedge.exe"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "Microsoft", "Edge", "Application", "msedge.exe"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "Google", "Chrome", "Application", "chrome.exe"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "Google", "Chrome", "Application", "chrome.exe"),
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Google", "Chrome", "Application", "chrome.exe")
        };

        foreach (string candidate in candidates)
        {
            if (!string.IsNullOrWhiteSpace(candidate) && File.Exists(candidate))
            {
                return candidate;
            }
        }

        return null;
    }
}
