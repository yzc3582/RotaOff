"""限时上架曲目表（摘录自 Rotaeno 中文维基）。

数据来源：Rotaeno 中文维基「限时上架曲目列表」（CC BY-NC-SA 3.0）
<https://wiki.rotaeno.cn/index.php?title=限时上架曲目列表>

曲目下架后，其全难度谱面不再参与 Rating / Completion 计算（来源同 wiki 条目说明）。
本表只用于把已下架曲目排除出 Best40，不影响单曲、状态、区间查询。
"""

import os
from datetime import date
from typing import Optional, Set

from sqlalchemy import Column, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class RetiredSongs:
    class RetiredSongModel(Base):
        __tablename__ = "retired_songs"

        id = Column(String, primary_key=True)
        title = Column(String, nullable=False)
        start_date = Column(String, nullable=False)
        end_date = Column(String, nullable=False)

    def __init__(self, database_path: str):
        self.engine = create_engine(f"sqlite:///{database_path}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get_retired_ids(self, today: Optional[date] = None) -> Set[str]:
        """下架日期 <= 今天的曲目 ID。"""
        today = today or date.today()
        session = self.Session()
        try:
            records = session.query(self.RetiredSongModel).filter(
                self.RetiredSongModel.end_date <= today.isoformat()
            ).all()
            return {record.id for record in records}
        finally:
            session.close()

    def is_retired(self, song_id: str, today: Optional[date] = None) -> bool:
        return song_id in self.get_retired_ids(today)

    def add_song(self, song_id: str, song_title: str, start_date: str, end_date: str) -> None:
        session = self.Session()
        try:
            session.merge(self.RetiredSongModel(
                id=song_id, title=song_title, start_date=start_date, end_date=end_date
            ))
            session.commit()
        except Exception as exc:
            session.rollback()
            print(f"Error updating retired song '{song_id}': {exc}")
        finally:
            session.close()


current_dir = os.path.dirname(os.path.abspath(__file__))
retired_songs = RetiredSongs(os.path.join(current_dir, "retired_songs.db"))