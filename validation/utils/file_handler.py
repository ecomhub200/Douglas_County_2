"""
File Handler Utility

Handles reading and writing CSV files for crash data,
with support for atomic writes and backup creation.
"""

import hashlib
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Set

import pandas as pd


class FileHandler:
    """
    Handles file operations for crash data validation.

    Features:
    - Safe CSV reading with error handling
    - Atomic writes (write to temp, then rename)
    - Backup creation before overwriting
    - Checksum calculation for integrity
    """

    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize file handler.

        Args:
            data_dir: Path to data directory. Defaults to project data folder.
        """
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data"

        self.data_dir = data_dir
        self.validation_dir = data_dir / ".validation"

    def read_csv(self, filename: str) -> pd.DataFrame:
        """
        Read CSV file from data directory.

        Args:
            filename: Name of CSV file

        Returns:
            DataFrame with file contents

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        filepath = self.data_dir / filename
        if not filepath.exists():
            raise FileNotFoundError(f"Data file not found: {filepath}")

        return pd.read_csv(filepath)

    def write_csv(self, df: pd.DataFrame, filename: str,
                  create_backup: bool = False) -> Path:
        """
        Write DataFrame to CSV file.

        Uses atomic write (temp file + rename) to prevent corruption.

        Args:
            df: DataFrame to write
            filename: Target filename
            create_backup: If True, backup existing file first

        Returns:
            Path to written file
        """
        filepath = self.data_dir / filename
        temp_path = filepath.with_suffix('.csv.tmp')

        # Create backup if requested and file exists
        if create_backup and filepath.exists():
            self._create_backup(filepath)

        # Write to temp file first
        df.to_csv(temp_path, index=False)

        # Atomic rename
        temp_path.replace(filepath)

        return filepath

    def _create_backup(self, filepath: Path):
        """Create timestamped backup of file."""
        backup_dir = self.validation_dir / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{filepath.stem}_{timestamp}{filepath.suffix}"
        backup_path = backup_dir / backup_name

        shutil.copy(filepath, backup_path)

    def load_validated_ids(self, jurisdiction: str, filter_type: str) -> Set[str]:
        """
        Load set of previously validated Document Numbers.

        Args:
            jurisdiction: Jurisdiction ID
            filter_type: Filter type (county_roads, no_interstate, all_roads)

        Returns:
            Set of validated Document Numbers
        """
        ids_file = self.validation_dir / f"validated_ids_{jurisdiction}_{filter_type}.txt"

        if not ids_file.exists():
            return set()

        with open(ids_file, 'r') as f:
            return set(
                line.strip() for line in f
                if line.strip() and not line.startswith('#')
            )

    def save_validated_ids(self, jurisdiction: str, filter_type: str,
                          ids: Set[str]):
        """
        Save validated Document Numbers.

        Args:
            jurisdiction: Jurisdiction ID
            filter_type: Filter type
            ids: Set of Document Numbers to save
        """
        self.validation_dir.mkdir(parents=True, exist_ok=True)
        ids_file = self.validation_dir / f"validated_ids_{jurisdiction}_{filter_type}.txt"

        with open(ids_file, 'w') as f:
            f.write(f"# Validated Document Numbers for {jurisdiction}_{filter_type}.csv\n")
            f.write(f"# Last updated: {datetime.utcnow().isoformat()}Z\n")
            f.write(f"# Total: {len(ids)}\n")
            for doc_id in sorted(ids):
                f.write(f"{doc_id}\n")

    def calculate_checksum(self, filepath: Path) -> str:
        """
        Calculate SHA256 checksum of file.

        Args:
            filepath: Path to file

        Returns:
            Hex string of SHA256 hash
        """
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def get_file_stats(self, filename: str) -> dict:
        """
        Get statistics about a data file.

        Args:
            filename: Name of CSV file

        Returns:
            Dict with records count, size, modified time, checksum
        """
        filepath = self.data_dir / filename
        if not filepath.exists():
            return {'exists': False}

        stat = filepath.stat()
        df = pd.read_csv(filepath)

        return {
            'exists': True,
            'records': len(df),
            'size_bytes': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'checksum': self.calculate_checksum(filepath)
        }

    def list_data_files(self, pattern: str = "*.csv") -> list:
        """
        List data files matching pattern.

        Args:
            pattern: Glob pattern (default: *.csv)

        Returns:
            List of matching filenames
        """
        return [f.name for f in self.data_dir.glob(pattern)]
