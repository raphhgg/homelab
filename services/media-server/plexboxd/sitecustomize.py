import builtins
import json
import sys
import time

from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException


def _page_has_challenge(html):
    lowered = html.lower()
    markers = ["cloudflare", "just a moment", "checking your browser", "cf-challenge", "challenge-platform"]
    return any(marker in lowered for marker in markers)


def _wait_until_not_challenged(driver, attempts=5, delay_seconds=3):
    for _ in range(attempts):
        if not _page_has_challenge(driver.page_source):
            return True
        time.sleep(delay_seconds)
        driver.refresh()
    return False


def _build_post_data(csrf_token, film_id, rating, viewing_date, rewatch, liked, tags, review):
    payload = [
        ("json", "true"),
        ("__csrf", csrf_token),
        ("viewingId", ""),
        ("filmId", str(film_id)),
        ("specifiedDate", "true"),
        ("viewingDateStr", viewing_date.strftime("%Y-%m-%d")),
        ("review", review or ""),
        ("rating", str(int(rating * 2))),
        ("liked", "true" if liked else "false"),
        ("rewatch", "true" if rewatch else "false"),
        ("reviewLanguageCodeHint", "en-US"),
    ]
    for tag in [t.strip() for t in (tags or "").replace(",", " ").split() if t.strip()]:
        payload.append(("tag", tag))
    return payload


def _apply_patch(lb):
    def patched_save_diary_entry(session, csrf_token, film_id, rating, viewing_date=None, rewatch=False, liked=False, tags="", review=""):
        if viewing_date:
            viewing_date_dt = lb.datetime.fromisoformat(viewing_date)
            if viewing_date_dt.hour < lb.DATE_THRESHOLD_HOUR:
                viewing_date_dt = viewing_date_dt - lb.timedelta(days=1)
        else:
            viewing_date_dt = lb.get_adjusted_date()

        lb.logger.info(
            f"Saving diary entry for film ID {film_id} with rating {rating}, liked={liked}, "
            f"rewatch={rewatch} for date {viewing_date_dt.strftime('%Y-%m-%d')}"
        )

        driver = lb.create_driver()
        try:
            driver.get("https://letterboxd.com/")
            for cookie in session.cookies:
                cookie_dict = {"name": cookie.name, "value": cookie.value}
                if getattr(cookie, "domain", None):
                    cookie_dict["domain"] = cookie.domain
                if getattr(cookie, "path", None):
                    cookie_dict["path"] = cookie.path
                try:
                    driver.add_cookie(cookie_dict)
                except Exception:
                    pass

            driver.refresh()
            time.sleep(2)
            if not _wait_until_not_challenged(driver):
                lb.logger.warning("Cloudflare challenge persisted before diary save")

            soup = BeautifulSoup(driver.page_source, "html.parser")
            csrf_elem = soup.find("input", {"name": "__csrf"})
            if csrf_elem and csrf_elem.get("value"):
                csrf_token = csrf_elem["value"]

            post_data = _build_post_data(csrf_token, film_id, rating, viewing_date_dt, rewatch, liked, tags, review)

            js = """
            const done = arguments[0];
            const payload = arguments[1];
            (async () => {
              const formData = new URLSearchParams();
              for (const pair of payload) formData.append(pair[0], pair[1]);
              try {
                const response = await fetch("https://letterboxd.com/s/save-diary-entry", {
                  method: "POST",
                  headers: {
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                    "Accept": "application/json, text/javascript, */*; q=0.01"
                  },
                  body: formData.toString(),
                  credentials: "include"
                });
                const text = await response.text();
                done(JSON.stringify({ok: true, status: response.status, text}));
              } catch (e) {
                done(JSON.stringify({ok: false, error: String(e)}));
              }
            })();
            """
            result = None
            try:
                driver.set_script_timeout(20)
                raw = driver.execute_async_script(js, post_data)
                result = json.loads(raw)
            except TimeoutException:
                lb.logger.warning("Browser fetch save timed out, using fallback POST")
            except Exception as e:
                lb.logger.warning(f"Browser fetch save exception: {e}")

            if result:
                if result.get("ok"):
                    try:
                        parsed = json.loads(result.get("text", ""))
                    except json.JSONDecodeError:
                        parsed = {}
                    if parsed.get("result") is True:
                        lb.logger.info(f"Successfully saved diary entry with {rating} stars")
                        return
                    lb.logger.warning(f"Browser fetch save failed status={result.get('status')} message={parsed.get('messages', result.get('text', '')[:180])}")
                else:
                    lb.logger.warning(f"Browser fetch save error: {result.get('error')}")

            for cookie in driver.get_cookies():
                session.cookies.set(cookie["name"], cookie["value"], domain=cookie.get("domain"))

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
                "Referer": "https://letterboxd.com/",
                "Origin": "https://letterboxd.com",
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            }
            response = session.post(lb.DIARY_URL, data=post_data, headers=headers, timeout=30)
            try:
                payload = response.json()
            except Exception:
                payload = {}
            if payload.get("result") is True:
                lb.logger.info(f"Successfully saved diary entry with {rating} stars")
                return
            message = payload.get("messages") or response.text[:240]
            raise ValueError(f"Failed to save diary entry: {message}")
        finally:
            driver.quit()

    lb.save_diary_entry = patched_save_diary_entry
    lb.logger.info("Applied runtime patch for Letterboxd diary save flow")


if "/app/src" not in sys.path:
    sys.path.insert(0, "/app/src")

try:
    import letterboxd_integration as _lb  # noqa: F401
    _apply_patch(_lb)
except Exception:
    _orig_import = builtins.__import__

    def _patched_import(name, globals=None, locals=None, fromlist=(), level=0):
        module = _orig_import(name, globals, locals, fromlist, level)
        if name == "letterboxd_integration":
            try:
                _apply_patch(module)
            except Exception:
                pass
            builtins.__import__ = _orig_import
        return module

    builtins.__import__ = _patched_import
