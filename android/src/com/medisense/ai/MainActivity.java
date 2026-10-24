package com.medisense.ai;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.text.InputType;
import android.view.Gravity;
import android.view.Menu;
import android.view.MenuItem;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.webkit.CookieManager;
import android.webkit.URLUtil;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

/**
 * MediSense AI Android client.
 *
 * The AI and the database run in the Django server (on a laptop on the same
 * Wi-Fi, or on a hosted server). This app stores the server address and shows
 * the MediSense web interface in a full-screen WebView, keeping the login
 * session, handling the back button and saving CSV reports to Downloads.
 */
public class MainActivity extends Activity {

    private static final String PREFS = "medisense";
    private static final String KEY_URL = "server_url";
    private static final String DEFAULT_URL = "http://192.168.1.5:8000";
    private static final int MENU_RELOAD = 1, MENU_SERVER = 2, MENU_HOME = 3;
    private static final int REQ_STORAGE = 7;

    private WebView webView;
    private ProgressBar progress;
    private String serverUrl;
    private String pendingDownload, pendingDisposition, pendingMime;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        serverUrl = prefs().getString(KEY_URL, null);
        if (serverUrl == null) {
            showSetup(null);
        } else {
            showWeb(state);
        }
    }

    private SharedPreferences prefs() {
        return getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    // ------------------------------------------------------------- setup screen
    private void showSetup(String error) {
        webView = null;
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(Color.parseColor("#F4F6F8"));
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(24), dp(32), dp(24), dp(32));
        scroll.addView(box);

        TextView title = new TextView(this);
        title.setText("MediSense AI");
        title.setTextSize(28);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        title.setTextColor(Color.parseColor("#134E4A"));
        box.addView(title);

        TextView sub = new TextView(this);
        sub.setText("Medicine expiry risk and inventory optimization");
        sub.setTextSize(15);
        sub.setTextColor(Color.parseColor("#475569"));
        sub.setPadding(0, dp(4), 0, dp(24));
        box.addView(sub);

        if (error != null) {
            TextView err = new TextView(this);
            err.setText(error);
            err.setTextColor(Color.parseColor("#B91C1C"));
            err.setPadding(0, 0, 0, dp(16));
            box.addView(err);
        }

        TextView label = new TextView(this);
        label.setText("Server address");
        label.setTypeface(Typeface.DEFAULT_BOLD);
        label.setTextColor(Color.parseColor("#0F172A"));
        box.addView(label);

        final EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_URI);
        input.setImeOptions(EditorInfo.IME_ACTION_GO);
        input.setHint(DEFAULT_URL);
        input.setText(serverUrl != null ? serverUrl : DEFAULT_URL);
        box.addView(input, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        Button connect = new Button(this);
        connect.setText("Connect");
        connect.setTextColor(Color.WHITE);
        connect.setBackgroundColor(Color.parseColor("#0F766E"));
        LinearLayout.LayoutParams bp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(52));
        bp.topMargin = dp(16);
        box.addView(connect, bp);

        TextView help = new TextView(this);
        help.setText("How to connect\n\n"
                + "1. On your laptop, open the MediSense project folder and run:\n"
                + "   python manage.py runserver 0.0.0.0:8000\n\n"
                + "2. Find the laptop's IP address:\n"
                + "   Windows: run ipconfig, look for IPv4 Address\n"
                + "   Linux / macOS: run ip addr or ifconfig\n\n"
                + "3. Connect the phone to the same Wi-Fi (or the laptop's hotspot).\n\n"
                + "4. Enter http://<laptop-IP>:8000 above, e.g. http://192.168.1.5:8000\n\n"
                + "If the server is hosted online, enter its https:// address instead.\n\n"
                + "Demo login: pharmacist / pharma@123");
        help.setTextSize(14);
        help.setTextColor(Color.parseColor("#334155"));
        help.setPadding(0, dp(28), 0, 0);
        help.setLineSpacing(0, 1.15f);
        box.addView(help);

        final View.OnClickListener go = new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String url = normalise(input.getText().toString());
                if (url == null) {
                    input.setError("Enter an address like http://192.168.1.5:8000");
                    return;
                }
                serverUrl = url;
                prefs().edit().putString(KEY_URL, url).apply();
                showWeb(null);
            }
        };
        connect.setOnClickListener(go);
        input.setOnEditorActionListener(new TextView.OnEditorActionListener() {
            @Override
            public boolean onEditorAction(TextView v, int actionId, android.view.KeyEvent e) {
                go.onClick(v);
                return true;
            }
        });
        setContentView(scroll);
        invalidateOptionsMenu();
    }

    static String normalise(String raw) {
        String url = raw == null ? "" : raw.trim();
        if (url.isEmpty()) return null;
        if (!url.startsWith("http://") && !url.startsWith("https://")) url = "http://" + url;
        while (url.endsWith("/")) url = url.substring(0, url.length() - 1);
        Uri u = Uri.parse(url);
        if (u.getHost() == null || u.getHost().isEmpty()) return null;
        return url;
    }

    // ------------------------------------------------------------- web screen
    private void showWeb(Bundle state) {
        FrameLayout root = new FrameLayout(this);
        webView = new WebView(this);
        root.addView(webView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        root.addView(progress, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, dp(4), Gravity.TOP));
        setContentView(root);

        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        s.setBuiltInZoomControls(true);
        s.setDisplayZoomControls(false);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, false);

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int p) {
                progress.setProgress(p);
                progress.setVisibility(p >= 100 ? View.GONE : View.VISIBLE);
            }

            @Override
            public void onReceivedTitle(WebView view, String t) {
                if (t != null) setTitle(t.replace(" | MediSense AI", ""));
            }
        });

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                Uri target = Uri.parse(url);
                Uri base = Uri.parse(serverUrl);
                if (target.getHost() != null && target.getHost().equals(base.getHost())) {
                    return false;               // stay inside the app
                }
                try {                            // other links open in the browser
                    startActivity(new Intent(Intent.ACTION_VIEW, target));
                } catch (Exception ignored) { }
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame()) {
                    showOffline(String.valueOf(err.getDescription()));
                }
            }

            @Override
            @SuppressWarnings("deprecation")
            public void onReceivedError(WebView view, int code, String desc, String url) {
                showOffline(desc);
            }
        });

        webView.setDownloadListener(new android.webkit.DownloadListener() {
            @Override
            public void onDownloadStart(String url, String ua, String disposition, String mime,
                                        long length) {
                download(url, disposition, mime);
            }
        });

        if (state != null) {
            webView.restoreState(state);
        } else {
            webView.loadUrl(serverUrl + "/");
        }
        invalidateOptionsMenu();
    }

    private void showOffline(String reason) {
        if (webView == null) return;
        String html = "<html><head><meta name='viewport' content='width=device-width,initial-scale=1'>"
                + "<style>body{font-family:sans-serif;padding:24px;color:#0f172a;background:#f4f6f8}"
                + "h2{color:#134e4a}code{background:#e2e8f0;padding:2px 6px;border-radius:4px}"
                + "a{display:block;margin-top:20px;padding:14px;background:#0f766e;color:#fff;"
                + "text-align:center;border-radius:8px;text-decoration:none}</style></head><body>"
                + "<h2>Cannot reach the MediSense server</h2>"
                + "<p>Address: <code>" + escape(serverUrl) + "</code></p>"
                + "<p>Error: " + escape(reason) + "</p>"
                + "<p>Check that:</p><ul>"
                + "<li>the server is running with <code>python manage.py runserver 0.0.0.0:8000</code></li>"
                + "<li>the phone and laptop are on the same Wi-Fi</li>"
                + "<li>the IP address is correct (run <code>ipconfig</code> on the laptop)</li>"
                + "<li>Windows Firewall allows Python on private networks</li></ul>"
                + "<a href='" + escape(serverUrl) + "/'>Try again</a>"
                + "<p style='margin-top:16px'>To change the address, open the menu (&#8942;) and tap "
                + "<b>Change server</b>.</p></body></html>";
        webView.loadDataWithBaseURL(serverUrl + "/", html, "text/html", "utf-8", serverUrl + "/");
    }

    private static String escape(String s) {
        if (s == null) return "";
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("'", "&#39;");
    }

    // ------------------------------------------------------------- CSV downloads
    private void download(String url, String disposition, String mime) {
        if (Build.VERSION.SDK_INT < 29
                && checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE)
                != PackageManager.PERMISSION_GRANTED) {
            pendingDownload = url;
            pendingDisposition = disposition;
            pendingMime = mime;
            requestPermissions(new String[]{Manifest.permission.WRITE_EXTERNAL_STORAGE}, REQ_STORAGE);
            return;
        }
        try {
            String name = URLUtil.guessFileName(url, disposition, mime);
            DownloadManager.Request r = new DownloadManager.Request(Uri.parse(url));
            String cookies = CookieManager.getInstance().getCookie(url);
            if (cookies != null) r.addRequestHeader("Cookie", cookies);
            r.setMimeType(mime);
            r.setTitle(name);
            r.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            r.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, name);
            ((DownloadManager) getSystemService(DOWNLOAD_SERVICE)).enqueue(r);
            Toast.makeText(this, "Saving " + name + " to Downloads", Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Toast.makeText(this, "Download failed: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    @Override
    public void onRequestPermissionsResult(int code, String[] perms, int[] results) {
        if (code == REQ_STORAGE && results.length > 0
                && results[0] == PackageManager.PERMISSION_GRANTED && pendingDownload != null) {
            download(pendingDownload, pendingDisposition, pendingMime);
        }
        pendingDownload = null;
    }

    // ------------------------------------------------------------- menu & lifecycle
    @Override
    public boolean onCreateOptionsMenu(Menu menu) {
        menu.clear();
        if (webView != null) {
            menu.add(0, MENU_HOME, 0, "Dashboard");
            menu.add(0, MENU_RELOAD, 1, "Reload");
            menu.add(0, MENU_SERVER, 2, "Change server");
        }
        return true;
    }

    @Override
    public boolean onOptionsItemSelected(MenuItem item) {
        switch (item.getItemId()) {
            case MENU_HOME:
                webView.loadUrl(serverUrl + "/");
                return true;
            case MENU_RELOAD:
                webView.reload();
                return true;
            case MENU_SERVER:
                new AlertDialog.Builder(this)
                        .setTitle("Change server")
                        .setMessage("Current: " + serverUrl)
                        .setPositiveButton("Change", new android.content.DialogInterface.OnClickListener() {
                            @Override
                            public void onClick(android.content.DialogInterface d, int w) {
                                showSetup(null);
                            }
                        })
                        .setNegativeButton("Cancel", null)
                        .show();
                return true;
        }
        return super.onOptionsItemSelected(item);
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        if (webView != null) webView.saveState(out);
    }

    @Override
    protected void onPause() {
        super.onPause();
        CookieManager.getInstance().flush();
    }
}
