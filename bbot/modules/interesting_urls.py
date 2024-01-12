from bbot.modules.deadly.ffuf import ffuf


class interesting_urls(ffuf):
    watched_events = ["URL"]
    produced_events = ["URL", "FINDING"]

    flags = ["aggressive", "active", "web-thorough"]
    meta = {"description": "Check URLs against a highly curated wordlist"}

    waf_strings = [
        "Web\\sPage\\sBlocked",
        "Sorry,\\ssomething\\swent\\swrong",
        "The\\srequested\\sURL\\swas\\srejected",
        "Error\\s404",
    ]

    in_scope_only = True

    canary = "#DUMMY#"

    async def setup(self):
        wordlist = f"{self.helpers.wordlist_dir}/interesting_urls.txt"
        self.debug(f"Using [{wordlist}] for shortname candidate list")
        self.wordlist = await self.helpers.wordlist(wordlist)
        self.wordlist_lines = list(self.helpers.read_file(self.wordlist))
        self.tempfile, tempfile_len = self.generate_templist()

        return True

    async def handle_event(self, event):
        # only FFUF against a directory
        if "." in event.parsed.path.split("/")[-1]:
            self.debug("Aborting FFUF as period was detected in right-most path segment (likely a file)")
            return
        else:
            # if we think its a directory, normalize it.
            fixed_url = event.data.rstrip("/") + "/"

        filters = {}
        filters[""] = ["-mc", "200"]
        filters[""] += ["-fr", "|".join(self.waf_strings)]

        # canary check
        canary_tempfile = self.helpers.tempfile(
            ["canary_check.aspx", "canary_check", "canary_check.php", "canary_check.jsp"], pipe=False
        )
        async for r in self.execute_ffuf(canary_tempfile, fixed_url, exts=[""], filters=filters):
            self.debug(f'Canary check triggered with canary URL: {r["url"]}')
            return False

        async for r in self.execute_ffuf(self.tempfile, fixed_url, exts=[""], filters=filters):
            self.emit_event(
                r["url"], "URL_UNVERIFIED", source=event, tags=[f"status-{r['status']}", "interesting-urls"]
            )
            self.emit_event(
                {"description": f"Interesting URL found: [{r['url']}]", "host": str(event.host), "url": r["url"]},
                "FINDING",
                source=event,
            )

    def generate_templist(self, prefix=None):
        line_count = 0

        virtual_file = []
        for idx, val in enumerate(self.wordlist_lines):
            if len(val) > 0:
                line_count += 1
                if "#" in val:
                    val = val.split("#")[0]
                virtual_file.append(f"{val.strip().lower()}")
        return self.helpers.tempfile(virtual_file, pipe=False), line_count

    async def filter_event(self, event):
        if "interesting-urls" in event.tags in event.tags:
            return False
        else:
            return True