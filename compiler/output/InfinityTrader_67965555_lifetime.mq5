#property strict
#property version "1.00"

input string MT5_ID       = "67965555";
input string EXPIRY       = "lifetime";
input string PLAN         = "Infinity Trader EA - Lifetime";
input string LICENSE_UUID = "";
input string API_BASE_URL = "https://infinity-trader-api-eq0o.onrender.com/api/v1";

// Re-checked on every tick, not just at init, so an account/clock change
// mid-session doesn't keep a revoked or expired license running until the
// next restart.
bool g_license_valid = false;

// Last known server-side verdict. Kept separate from g_license_valid so a
// temporary network failure doesn't get confused with an actual server
// "revoked" response — see CheckServerStatus() below.
bool g_server_says_revoked = false;

//+------------------------------------------------------------------+
//| Compare MT5_ID against the account this EA is actually running on |
//+------------------------------------------------------------------+
bool CheckAccountMatch()
{
   string account_login = IntegerToString((int)AccountInfoInteger(ACCOUNT_LOGIN));
   if(account_login != MT5_ID)
     {
      Print("LICENSE ERROR: EA is licensed to account ", MT5_ID,
            " but is running on account ", account_login);
      return(false);
     }
   return(true);
}

//+------------------------------------------------------------------+
//| Parse "YYYY-MM-DD" and compare against the current server time.   |
//| EXPIRY == "lifetime" always passes.                               |
//+------------------------------------------------------------------+
bool CheckExpiry()
{
   if(EXPIRY == "lifetime")
      return(true);

   if(StringLen(EXPIRY) != 10 || StringGetCharacter(EXPIRY, 4) != '-' || StringGetCharacter(EXPIRY, 7) != '-')
     {
      Print("LICENSE ERROR: malformed expiry string '", EXPIRY, "'");
      return(false);
     }

   int year  = (int)StringToInteger(StringSubstr(EXPIRY, 0, 4));
   int month = (int)StringToInteger(StringSubstr(EXPIRY, 5, 2));
   int day   = (int)StringToInteger(StringSubstr(EXPIRY, 8, 2));

   MqlDateTime expiry_struct;
   TimeToStruct(TimeCurrent(), expiry_struct); // zero-init struct via a valid time first
   expiry_struct.year  = year;
   expiry_struct.mon   = month;
   expiry_struct.day   = day;
   expiry_struct.hour  = 23;
   expiry_struct.min   = 59;
   expiry_struct.sec   = 59;

   datetime expiry_time = StructToTime(expiry_struct);

   if(TimeCurrent() > expiry_time)
     {
      Print("LICENSE ERROR: license expired on ", EXPIRY,
            " (current time ", TimeToString(TimeCurrent(), TIME_DATE), ")");
      return(false);
     }
   return(true);
}

//+------------------------------------------------------------------+
//| Very small JSON scraper — good enough for a flat, known response  |
//| shape like {"status":"active","expiry_date":"2026-12-31"}. Avoids |
//| pulling in a full JSON library for one field.                     |
//+------------------------------------------------------------------+
string ExtractJsonStringField(const string &json, const string field)
{
   string needle = "\"" + field + "\":\"";
   int start = StringFind(json, needle);
   if(start < 0)
      return("");
   start += StringLen(needle);
   int end = StringFind(json, "\"", start);
   if(end < 0)
      return("");
   return(StringSubstr(json, start, end - start));
}

//+------------------------------------------------------------------+
//| Call the backend heartbeat endpoint. Updates g_server_says_revoked|
//| only on a successful, parseable response — a network error or an  |
//| unreachable server leaves the last-known verdict unchanged, so a  |
//| VPS with a flaky connection doesn't get treated as revoked just   |
//| for missing one check-in. An explicit "revoked"/"expired"/        |
//| "not_found" from the server DOES stop the EA even if the local    |
//| account/expiry check above still passes — that's the whole point: |
//| it lets you kill a license after the binary is already deployed.  |
//+------------------------------------------------------------------+
void CheckServerStatus()
{
   if(LICENSE_UUID == "" || API_BASE_URL == "")
      return; // no server-side revocation configured for this build

   string url = API_BASE_URL + "/licenses/status/" + LICENSE_UUID;
   string headers = "";
   char post_data[];
   char result[];
   string result_headers;

   ResetLastError();
   int res = WebRequest("GET", url, headers, 5000, post_data, result, result_headers);

   if(res == -1)
     {
      int err = GetLastError();
      if(err == 4014)
         Print("LICENSE WARNING: WebRequest blocked — add '", API_BASE_URL,
               "' to Tools > Options > Expert Advisors > Allow WebRequest for listed URL.");
      else
         Print("LICENSE WARNING: heartbeat request failed, error ", err, " — using last known status.");
      return;
     }

   string response = CharArrayToString(result);
   string status = ExtractJsonStringField(response, "status");

   if(status == "active")
      g_server_says_revoked = false;
   else if(status == "revoked" || status == "expired" || status == "not_found")
     {
      if(!g_server_says_revoked)
         Print("LICENSE ERROR: server reports license status '", status, "' — EA will stop trading.");
      g_server_says_revoked = true;
     }
   // Any other/unrecognized response: leave last known verdict unchanged
   // rather than guessing.
}

bool ValidateLicense()
{
   bool account_ok = CheckAccountMatch();
   bool expiry_ok  = CheckExpiry();
   return(account_ok && expiry_ok && !g_server_says_revoked);
}

int OnInit()
{
   Print("Infinity Trader EA initialized");
   Print("MT5 ID: ", MT5_ID);
   Print("Expiry: ", EXPIRY);
   Print("Plan: ", PLAN);

   CheckServerStatus();
   g_license_valid = ValidateLicense();
   if(!g_license_valid)
     {
      Alert("Infinity Trader: license check failed — EA will not trade. See Experts log for details.");
      // Deliberately still return INIT_SUCCEEDED rather than INIT_FAILED:
      // MT5 fully unloads an EA that fails OnInit, which means it stops
      // appearing in the terminal and stops calling OnTick() again on its
      // own, but a user could simply re-attach it and get a fresh OnInit
      // pass — INIT_FAILED alone is not a stronger gate than the per-tick
      // check below, so we rely on g_license_valid gating OnTick() instead.
     }

   // Re-validate periodically: local account/expiry check plus a server
   // heartbeat, so a clock rollback, expiry crossing, or an admin revoking
   // the license after deployment all take effect without an EA restart.
   EventSetTimer(3600); // hourly

   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTimer()
{
   CheckServerStatus();
   g_license_valid = ValidateLicense();
}

void OnTick()
{
   if(!g_license_valid)
      return;

   // NOTE: there is no trading logic in this template to gate. This block
   // only proves/enforces the license; it does not implement a strategy.
}