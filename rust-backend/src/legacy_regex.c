/* KEY_RE is inert, but configuration validation follows the shell's grep -E.
 * glibc's POSIX regcomp rejects GNU egrep's leading repetition operators and
 * literal malformed intervals. Use its egrep syntax, without spawning grep.
 * The bridge validates one config before transport starts; the GNU syntax
 * setting is process-global and is restored immediately after compilation. */
#define _GNU_SOURCE
#include <regex.h>
#include <string.h>

int jira_peek_valid_ere(const char *pattern) {
    regex_t expression = {0};
#ifdef __GLIBC__
    reg_syntax_t previous = re_set_syntax(RE_SYNTAX_EGREP);
    int valid = re_compile_pattern(pattern, strlen(pattern), &expression) == NULL;
    re_set_syntax(previous);
    regfree(&expression);
    return valid;
#else
    int flags = REG_EXTENDED | REG_NOSUB;
#ifdef __APPLE__
    /* Darwin grep enables this mode; among other things it rejects a
     * backreference without a preceding group instead of accepting it. */
    flags |= REG_ENHANCED;
#endif
    if (regcomp(&expression, pattern, flags) != 0) return 0;
    regfree(&expression);
    return 1;
#endif
}
