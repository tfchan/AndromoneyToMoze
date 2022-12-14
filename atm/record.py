from __future__ import annotations  # Fix annotation error of returning Record

import datetime
import warnings
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd


DIFFERENT_CURRENCY_WARNING = ('Pleass be aware that AndroMoney does not '
                              'preserve the amount you received when'
                              'transfering between different currency, '
                              'you have to manually adjust it.')


class RecordType(Enum):
    INCOME = 'Income'
    EXPENSE = 'Expense'
    TRANSFER = 'Transfer'


@dataclass
class Record:
    from_account: str
    to_account: str
    from_amount: float
    to_amount: float
    from_currency: str
    to_currency: str
    categories: list[str]
    date: datetime.date
    time: datetime.time = None
    shop: str = None
    title: str = None
    detail: str = None
    project: str = None
    record_type: RecordType = field(init=False)

    def __post_init__(self) -> None:
        if (not (self.from_account or self.to_account)
                or (self.from_amount is None and self.to_amount is None)
                or not (self.from_currency or self.to_currency)):
            raise ValueError('Both from and to Account/Amount/Currency '
                             'are None or empty')

        if self.from_account and self.to_account:
            self.record_type = RecordType.TRANSFER
        elif self.from_account:
            self.record_type = RecordType.EXPENSE
        else:
            self.record_type = RecordType.INCOME

    @classmethod
    def from_andromoney(cls, record: pd.Series) -> Record:
        warnings.warn(DIFFERENT_CURRENCY_WARNING)
        record = record.replace(pd.NA, None)
        match record["Category"], record["Amount"]:
            case 'SYSTEM', 0:
                return None
            case 'SYSTEM', _:
                raise ValueError(f'Account {record["Income(Transfer In)"]} '
                                 'was created with initial amount, please '
                                 'make it as an income record with proper '
                                 'date')

        date = pd.to_datetime(record["Date"], format='%Y%m%d').date()
        time = (pd.to_datetime(f'{int(record["Time"]):04}', format='%H%M')
                .time() if pd.notna(record["Time"]) else None)
        return cls(record["Expense(Transfer Out)"],
                   record["Income(Transfer In)"],
                   record["Amount"],
                   record["Amount"],
                   record["Currency"],
                   record["Currency"],
                   [record["Category"], record["Sub-Category"]],
                   date,
                   time=time,
                   shop=record["Payee/Payer"],
                   detail=record["Remark"],
                   project=record["Project"]
                   )

    def to_moze(self) -> pd.DataFrame:
        if self.record_type not in [RecordType.EXPENSE,
                                    RecordType.INCOME,
                                    RecordType.TRANSFER]:
            raise ValueError(f'Conversion of {self.record_type} Record'
                             'to Moze is not supported')

        record = {
            'Account': [self.from_account, self.to_account],
            'Currency': [self.from_currency, self.to_currency],
            'Type': ['Expense', 'Income'],
            'Main Category': [self.categories[0]] * 2,
            'Subcategory': [self.categories[1]] * 2,
            'Price': [-self.from_amount, self.to_amount],
            'Fee': [pd.NA] * 2,
            'Bonus': [pd.NA] * 2,
            'Name': [self.title] * 2,
            'Store': [self.shop] * 2,
            'Date': [self.date.strftime('%Y/%m/%d')] * 2,
            'Time': [self.time.strftime('%H:%M') if self.time else pd.NA] * 2,
            'Project': [self.project] * 2,
            'Description': [self.detail] * 2,
            'Tag': [pd.NA] * 2,
            'Target': [pd.NA] * 2
        }

        if self.record_type == RecordType.TRANSFER:
            record["Type"] = ['Transfer Out', 'Transfer In']
            return pd.DataFrame(record)
        r = 0 if self.record_type == RecordType.EXPENSE else 1
        return pd.DataFrame(record).iloc[r:r + 1]
