# Rust Filesystem MCP Server

The Rust MCP Filesystem is a high-performance, asynchronous, and lightweight Model Context Protocol (MCP) server built in Rust for secure and efficient filesystem operations. Designed with security in mind, it operates in read-only mode by default and restricts clients from updating allowed directories via MCP Roots unless explicitly enabled, ensuring robust protection against unauthorized access. Leveraging asynchronous I/O, it delivers blazingly fast performance with a minimal resource footprint.
Optimized for token efficiency, the Rust MCP Filesystem enables large language models (LLMs) to precisely target searches and edits within specific sections of large files and restrict operations by file size range, making it ideal for efficient file exploration, automation, and system integration.

[What is an MCP Server?](https://www.anthropic.com/news/model-context-protocol)

## MCP Info
Attribute|Details|
|-|-|
**Docker Image**|[mcp/rust-mcp-filesystem](https://hub.docker.com/repository/docker/mcp/rust-mcp-filesystem)
**Author**|[rust-mcp-stack](https://github.com/rust-mcp-stack)
**Repository**|https://github.com/rust-mcp-stack/rust-mcp-filesystem

## Image Building Info
Attribute|Details|
|-|-|
**Dockerfile**|https://github.com/rust-mcp-stack/rust-mcp-filesystem/blob/aa9af19d7cefe2657ca7ae32893b88049eb1f85a/Dockerfile
**Commit**|`aa9af19d7cefe2657ca7ae32893b88049eb1f85a`
**Docker Image built by**|Docker Inc.
**Docker Scout Health Score**| ![Docker Scout Health Score](https://api.scout.docker.com/v1/policy/insights/org-image-score/badge/mcp/rust-mcp-filesystem)
**Verify Signature**|`COSIGN_REPOSITORY=mcp/signatures cosign verify mcp/rust-mcp-filesystem --key https://raw.githubusercontent.com/docker/keyring/refs/heads/main/public/mcp/latest.pub`
**Licence**|MIT License

## Available Tools (24)
Tools provided by this Server|Short Description
-|-
`calculate_directory_size`|Calculates the total size of a directory specified by `root_path`.It recursively searches for files and sums their sizes.|
`create_directory`|Create a new directory or ensure a directory exists.|
`directory_tree`|Get a recursive tree view of files and directories as a JSON structure.|
`edit_file`|Make line-based edits to a text file.|
`find_duplicate_files`|Find duplicate files within a directory and return list of duplicated files as text or json formatOptional `pattern` argument can be used to narrow down the file search to specific glob pattern.Optional `exclude_patterns` can be used to exclude certain files matching a glob.`min_bytes` and `max_bytes` are optional arguments that can be used to restrict the search to files with sizes within a specified range.The output_format argument specifies the format of the output and accepts either `text` or `json` (default: text).Only works within allowed directories.|
`find_empty_directories`|Recursively finds all empty directories within the given root path.A directory is considered empty if it contains no files in itself or any of its subdirectories.Operating system metadata files `.DS_Store` (macOS) and `Thumbs.db` (Windows) will be ignored.The optional exclude_patterns argument accepts glob-style patterns to exclude specific paths from the search.Only works within allowed directories.|
`get_file_info`|Retrieve detailed metadata about a file or directory.|
`head_file`|Reads and returns the first N lines of a text file.This is useful for quickly previewing file contents without loading the entire file into memory.If the file has fewer than N lines, the entire file will be returned.Only works within allowed directories.|
`list_allowed_directories`|Returns a list of directories that the server has permission to access Subdirectories within these allowed directories are also accessible.|
`list_directory`|Get a detailed listing of all files and directories in a specified path.|
`list_directory_with_sizes`|Get a detailed listing of all files and directories in a specified path, including sizes.|
`move_file`|Move or rename files and directories.|
`read_file_lines`|Reads lines from a text file starting at a specified line offset (0-based) and continues for the specified number of lines if a limit is provided.This function skips the first 'offset' lines and then reads up to 'limit' lines if specified, or reads until the end of the file otherwise.It's useful for partial reads, pagination, or previewing sections of large text files.Only works within allowed directories.|
`read_media_file`|Reads an image or audio file and returns its Base64-encoded content along with the corresponding MIME type.|
`read_multiple_media_files`|Reads multiple image or audio files and returns their Base64-encoded contents along with corresponding MIME types.|
`read_multiple_text_files`|Read the contents of multiple text files simultaneously as text.|
`read_text_file`|Read the complete contents of a text file from the file system as text.|
`search_files`|Recursively search for files and directories matching a pattern.|
`search_files_content`|Searches for text or regex patterns in the content of files matching matching a GLOB pattern.Returns detailed matches with file path, line number, column number and a preview of matched text.By default, it performs a literal text search; if the 'is_regex' parameter is set to true, it performs a regular expression (regex) search instead.Optional 'min_bytes' and 'max_bytes' arguments can be used to filter files by size, ensuring that only files within the specified byte range are included in the search.|
`tail_file`|Reads and returns the last N lines of a text file.This is useful for quickly previewing file contents without loading the entire file into memory.If the file has fewer than N lines, the entire file will be returned.Only works within allowed directories.|
`unzip_file`|Extracts the contents of a ZIP archive to a specified target directory.|
`write_file`|Create a new file or completely overwrite an existing file with new content.|
`zip_directory`|Creates a ZIP archive by compressing a directory , including files and subdirectories matching a specified glob pattern.|
`zip_files`|Creates a ZIP archive by compressing files.|

---
## Tools Details

#### Tool: **`calculate_directory_size`**
Calculates the total size of a directory specified by `root_path`.It recursively searches for files and sums their sizes. The result can be returned in either a `human-readable` format or as `bytes`, depending on the specified `output_format` argument.Only works within allowed directories.
Parameters|Type|Description
-|-|-
`root_path`|`string`|The root directory path to start the size calculation.
`output_format`|`string` *optional*|Defines the output format, which can be either `human-readable` or `bytes`.

*This tool is read-only. It does not modify its environment.*

---
#### Tool: **`create_directory`**
Create a new directory or ensure a directory exists. Can create multiple nested directories in one operation. If the directory already exists, this operation will succeed silently. Perfect for setting up directory structures for projects or ensuring required paths exist. Only works within allowed directories.
Parameters|Type|Description
-|-|-
`path`|`string`|The path where the directory will be created.

---
#### Tool: **`directory_tree`**
Get a recursive tree view of files and directories as a JSON structure. Each entry includes 'name', 'type' (file/directory), and 'children' for directories. Files have no children array, while directories always have a children array (which may be empty). If the 'max_depth' parameter is provided, the traversal will be limited to the specified depth. As a result, the returned directory structure may be incomplete or provide a skewed representation of the full directory tree, since deeper-level files and subdirectories beyond the specified depth will be excluded. The output is formatted with 2-space indentation for readability. Only works within allowed directories.
Parameters|Type|Description
-|-|-
`path`|`string`|The root path of the directory tree to generate.
`max_depth`|`integer` *optional*|Limits the depth of directory traversal

*This tool is read-only. It does not modify its environment.*

---
#### Tool: **`edit_file`**
Make line-based edits to a text file. Each edit replaces exact line sequences with new content. Returns a git-style diff showing the changes made. Only works within allowed directories.
Parameters|Type|Description
-|-|-
`edits`|`array`|The list of edit operations to apply.
`path`|`string`|The path of the file to edit.
`dryRun`|`boolean` *optional*|Preview changes using git-style diff format without applying them.
`replaceAll`|`boolean` *optional*|Optional flag to replace all occurrences of `oldText`.

Default: `false`.
- `false` or `null` â†’ if multiple matches are found, an error is returned.
- `true`  â†’ replace all matches.

---
#### Tool: **`find_duplicate_files`**
Find duplicate files within a directory and return list of duplicated files as text or json formatOptional `pattern` argument can be used to narrow down the file search to specific glob pattern.Optional `exclude_patterns` can be used to exclude certain files matching a glob.`min_bytes` and `max_bytes` are optional arguments that can be used to restrict the search to files with sizes within a specified range.The output_format argument specifies the format of the output and accepts either `text` or `json` (default: text).Only works within allowed directories.
Parameters|Type|Description
-|-|-
`root_path`|`string`|The root directory path to start the search.
`exclude_patterns`|`array` *optional*|Optional list of glob patterns to exclude from the search. File matching these patterns will be ignored.
`max_bytes`|`integer` *optional*|Maximum file size (in bytes) to include in the search (optional).
`min_bytes`|`integer` *optional*|Minimum file size (in bytes) to include in the search (default to 1).
`output_format`|`string` *optional*|Specify the output format, accepts either `text` or `json` (default: text).
`pattern`|`string` *optional*|Optional glob pattern can be used to match target files.

*This tool is read-only. It does not modify its environment.*

---
#### Tool: **`find_empty_directories`**
Recursively finds all empty directories within the given root path.A directory is considered empty if it contains no files in itself or any of its subdirectories.Operating system metadata files `.DS_Store` (macOS) and `Thumbs.db` (Windows) will be ignored.The optional exclude_patterns argument accepts glob-style patterns to exclude specific paths from the search.Only works within allowed directories.
Parameters|Type|Description
-|-|-
`path`|`string`|The path of the file to get information for.
`exclude_patterns`|`array` *optional*|Optional list of glob patterns to exclude from the search. Directories matching these patterns will be ignored.
`output_format`|`string` *optional*|Specify the output format, accepts either `text` or `json` (default: text).

*This tool is read-only. It does not modify its environment.*

---
#### Tool: **`get_file_info`**
Retrieve detailed metadata about a file or directory. Returns comprehensive information including size, creation time, last modified time, permissions, and type. This tool is perfect for understanding file characteristics without reading the actual content. Only works within allowed directories.
Parameters|Type|Description
-|-|-
`path`|`string`|The path of the file to get information for.

*This tool is read-only. It does not modify its environment.*

---
#### Tool: **`head_file`**
Reads and returns the first N lines of a text file.This is useful for quickly previewing file contents without loading the entire file into memory.If the file has fewer than N lines, the entire file will be returned.Only works within allowed directories.
Parameters|Type|Description
-|-|-
`lines`|`integer`|The number of lines to read from the beginning of the file.
`path`|`string`|The path of the file to get information for.

*This tool is read-only. It does not modify its environment.*

---
#### Tool: **`list_allowed_directories`**
Returns a list of directories that the server has permission to access Subdirectories within these allowed directories are also accessible. Use this to identify which directories and their nested paths are available before attempting to access files.
#### Tool: **`list_directory`**
Get a detailed listing of all files and directories in a specified path. Results clearly distinguish between files and directories with [FILE] and [DIR] prefixes. This tool is essential for understanding directory structure and finding specific files within a directory. Only works within allowed directories.
Parameters|Type|Description
-|-|-
`path`|`string`|The path of the directory to list.

*This tool is read-only. It does not modify its environment.*

---
#### Tool: **`list_directory_with_sizes`**
Get a detailed listing of all files and directories in a specified path, including sizes. Results clearly distinguish between files and directories with [FILE] and [DIR] prefixes. This tool is useful for understanding directory structure and finding specific files within a directory. Only works within allowed directories.
Parameters|Type|Description
-|-|-
`path`|`string`|The path of the directory to list.

*This tool is read-only. It does not modify its environment.*

---
#### Tool: **`move_file`**
Move or rename files and directories. Can move files between directories and rename them in a single operation. If the destination exists, the operation will fail. Works across different directories and can be used for simple renaming within the same directory. Both source and destination must be within allowed directories.
Parameters|Type|Description
-|-|-
`destination`|`string`|The destination path to move the file to.
`source`|`string`|The source path of the file to move.

---
#### Tool: **`read_file_lines`**
Reads lines from a text file starting at a specified line offset (0-based) and continues for the specified number of lines if a limit is provided.This function skips the first 'offset' lines and then reads up to 'limit' lines if specified, or reads until the end of the file otherwise.It's useful for partial reads, pagination, or previewing sections of large text files.Only works within allowed directories.
Parameters|Type|Description
-|-|-
`offset`|`integer`|Number of lines to skip from the start (0-based).
`path`|`string`|The path of the file to get information for.
`limit`|`integer` *optional*|Optional maximum number of lines to read after the offset.

*This tool is read-only. It does not modify its environment.*

---
#### Tool: **`read_media_file`**
Reads an image or audio file and returns its Base64-encoded content along with the corresponding MIME type. The max_bytes argument could be used to enforce an upper limit on the size of a file to read if the media file exceeds this limit, the operation will return an error instead of reading the media file. Access is restricted to files within allowed directories only.
Parameters|Type|Description
-|-|-
`path`|`string`|The path of the file to read.
`max_bytes`|`integer` *optional*|Maximum allowed file size (in bytes) to be read.

*This tool is read-only. It does not modify its environment.*

---
#### Tool: **`read_multiple_media_files`**
Reads multiple image or audio files and returns their Base64-encoded contents along with corresponding MIME types. This method is more efficient than reading files individually. The max_bytes argument could be used to enforce an upper limit on the size of a file to read Failed reads for specific files are skipped without interrupting the entire operation. Only works within allowed directories.
Parameters|Type|Description
-|-|-
`paths`|`array`|The list of media file paths to read.
`max_bytes`|`integer` *optional*|Maximum allowed file size (in bytes) to be read.

*This tool is read-only. It does not modify its environment.*

---
#### Tool: **`read_multiple_text_files`**
Read the contents of multiple text files simultaneously as text. This is more efficient than reading files one by one when you need to analyze or compare multiple files. Each file's content is returned with its path as a reference. Failed reads for individual files won't stop the entire operation. Only works within allowed directories.
Parameters|Type|Description
-|-|-
`paths`|`array`|The list of file paths to read.

*This tool is read-only. It does not modify its environment.*

---
#### Tool: **`read_text_file`**
Read the complete contents of a text file from the file system as text. Handles various text encodings and provides detailed error messages if the file cannot be read. Use this tool when you need to examine the contents of a single file. Optionally include line numbers for precise code targeting. Only works within allowed directories.
Parameters|Type|Description
-|-|-
`path`|`string`|The path of the file to read.
`with_line_numbers`|`boolean` *optional*|Optional: Include line numbers in output (default: false).
When enabled, each line is prefixed with a right-aligned, 1-based line number
Followed by a space, a vertical bar (`|`), and another space in the format: `   123 | <original line content>`

*This tool is read-only. It does not modify its environment.*

---
#### Tool: **`search_files`**
Recursively search for files and directories matching a pattern. Searches through all subdirectories from the starting path. The search is case-insensitive and matches partial names. Returns full paths to all matching items.Optional 'min_bytes' and 'max_bytes' arguments can be used to filter files by size, ensuring that only files within the specified byte range are included in the search. This tool is great for finding files when you don't know their exact location or find files by their size.Only searches within allowed directories.
Parameters|Type|Description
-|-|-
`path`|`string`|The directory path to search in.
`pattern`|`string`|Glob pattern used to match target files (e.g., "*.rs").
`excludePatterns`|`array` *optional*|Optional list of patterns to exclude from the search.
`max_bytes`|`integer` *optional*|Maximum file size (in bytes) to include in the search (optional).
`min_bytes`|`integer` *optional*|Minimum file size (in bytes) to include in the search (optional).

*This tool is read-only. It does not modify its environment.*

---
#### Tool: **`search_files_content`**
Searches for text or regex patterns in the content of files matching matching a GLOB pattern.Returns detailed matches with file path, line number, column number and a preview of matched text.By default, it performs a literal text search; if the 'is_regex' parameter is set to true, it performs a regular expression (regex) search instead.Optional 'min_bytes' and 'max_bytes' arguments can be used to filter files by size, ensuring that only files within the specified byte range are included in the search. Ideal for finding specific code, comments, or text when you donâ€™t know their exact location.
Parameters|Type|Description
-|-|-
`path`|`string`|The file or directory path to search in.
`pattern`|`string`|The file glob pattern to match (e.g., "*.rs").
`query`|`string`|Text or regex pattern to find in file contents (e.g., 'TODO' or '^function\\s+').
`excludePatterns`|`array` *optional*|Optional list of patterns to exclude from the search.
`is_regex`|`boolean` *optional*|Whether the query is a regular expression. If false, the query as plain text. (Default : false)
`max_bytes`|`integer` *optional*|Maximum file size (in bytes) to include in the search (optional).
`min_bytes`|`integer` *optional*|Minimum file size (in bytes) to include in the search (optional).

*This tool is read-only. It does not modify its environment.*

---
#### Tool: **`tail_file`**
Reads and returns the last N lines of a text file.This is useful for quickly previewing file contents without loading the entire file into memory.If the file has fewer than N lines, the entire file will be returned.Only works within allowed directories.
Parameters|Type|Description
-|-|-
`lines`|`integer`|The number of lines to read from the ending of the file.
`path`|`string`|The path of the file to get information for.

*This tool is read-only. It does not modify its environment.*

---
#### Tool: **`unzip_file`**
Extracts the contents of a ZIP archive to a specified target directory.
It takes a source ZIP file path and a target extraction directory.
The tool decompresses all files and directories stored in the ZIP, recreating their structure in the target location.
Both the source ZIP file and the target directory should reside within allowed directories.
Parameters|Type|Description
-|-|-
`target_path`|`string`|Path to the target directory where the contents of the ZIP file will be extracted.
`zip_file`|`string`|A filesystem path to an existing ZIP file to be extracted.

---
#### Tool: **`write_file`**
Create a new file or completely overwrite an existing file with new content. Use with caution as it will overwrite existing files without warning. Handles text content with proper encoding. Only works within allowed directories.
Parameters|Type|Description
-|-|-
`content`|`string`|The content to write to the file.
`path`|`string`|The path of the file to write to.

---
#### Tool: **`zip_directory`**
Creates a ZIP archive by compressing a directory , including files and subdirectories matching a specified glob pattern.
It takes a path to the folder and a glob pattern to identify files to compress and a target path for the resulting ZIP file.
Both the source directory and the target ZIP file should reside within allowed directories.
Parameters|Type|Description
-|-|-
`input_directory`|`string`|Path to the directory to zip
`target_zip_file`|`string`|Path to save the resulting ZIP file, including filename and .zip extension
`pattern`|`string` *optional*|A optional glob pattern to match files and subdirectories to zip, defaults to **/*"

---
#### Tool: **`zip_files`**
Creates a ZIP archive by compressing files. It takes a list of files to compress and a target path for the resulting ZIP file. Both the source files and the target ZIP file should reside within allowed directories.
Parameters|Type|Description
-|-|-
`input_files`|`array`|The list of files to include in the ZIP archive.
`target_zip_file`|`string`|Path to save the resulting ZIP file, including filename and .zip extension

---
## Use this MCP Server

```json
{
  "mcpServers": {
    "rust-mcp-filesystem": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "ENABLE_ROOTS",
        "-e",
        "ALLOW_WRITE",
        "-v",
        "/local-directory:/local-directory",
        "mcp/rust-mcp-filesystem",
        "{{rust-mcp-filesystem.allowed_directories|volume-target|into}}"
      ],
      "env": {
        "ENABLE_ROOTS": "false",
        "ALLOW_WRITE": "false"
      }
    }
  }
}