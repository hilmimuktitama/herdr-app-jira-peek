//! Apply the exact managed netrc format independently of libcurl's parser version.
use crate::{fail, Result};
use curl::easy::{Easy, NetRc};
use std::{ffi::CString, path::Path};

pub(crate) fn apply(easy: &mut Easy, path: &Path, bytes: &[u8], host: &str) -> Result<()> {
    if bytes.starts_with(b"# herdr-jira-peek-managed:") {
        // curl before 7.84 treats quotes as credential bytes. Keep the private
        // on-disk format compatible with older helpers, but pass our validated
        // fields directly to libcurl. Never interpret arbitrary netrc syntax.
        let text = std::str::from_utf8(bytes).map_err(|_| fail("connection_failed"))?;
        let pattern = regex::Regex::new(
            r##"\A# herdr-jira-peek-managed:[0-9a-f]{48}\nmachine ([a-z0-9.-]+) login "([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+)" password "([^"\\\s]+)"\n\z"##,
        ).unwrap();
        let fields = pattern.captures(text).ok_or(fail("connection_failed"))?;
        if !fields[1].eq_ignore_ascii_case(host)
            || fields[3].len() > 4096
            || !fields[3].bytes().all(|b| (33..127).contains(&b))
        {
            return Err(fail("connection_failed"));
        }
        easy.netrc(NetRc::Ignored)?;
        easy.username(&fields[2])?;
        easy.password(&fields[3])?;
    } else {
        let file = CString::new(path.as_os_str().as_encoded_bytes())
            .map_err(|_| fail("connection_failed"))?;
        easy.netrc(NetRc::Required)?;
        // libcurl copies this option's string; the CString need not outlive it.
        unsafe {
            if curl_sys::curl_easy_setopt(easy.raw(), curl_sys::CURLOPT_NETRC_FILE, file.as_ptr())
                != curl_sys::CURLE_OK
            {
                return Err(fail("connection_failed"));
            }
        }
    }
    Ok(())
}
