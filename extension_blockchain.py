import hashlib
import datetime
import time
import json
import random


# 難易度
INITIAL_BITS = 0x1d777777
# 最大値
MAX_32BIT = 0xffffffff


class Block():
    '''
    個々のブロックを構築
    '''

    def __init__(self, index, prev_hash, data, timestamp, bits):
        '''
        初期化
        '''

        self.index = index
        self.prev_hash = prev_hash
        self.data = data
        self.timestamp = timestamp
        self.bits = bits
        self.nonce = 0
        self.elapsed_time = ''
        self.block_hash = ''

    def __setitem__(self, key, value):
        '''
        オブジェクトを辞書型で扱う（特殊メソッド）
        '''

        # 属性を追加（第1引数：オブジェクト、第2引数：属性名、第3引数：属性値）
        setattr(self, key, value)

    def to_json(self):
        '''
        1つのブロックにまとめる
        '''

        # rjust：全部で8文字になるように右寄せ
        return {
            'index': self.index,
            'prev_hash': self.prev_hash,
            'stored_data': self.data,
            'timestamp': self.timestamp.strftime('%Y/%m/%d %H:%M:%S'),
            'bits': hex(self.bits)[2:].rjust(8, '0'),
            'nonce': hex(self.nonce)[2:].rjust(8, '0'),
            'elapsed_time': self.elapsed_time,
            'block_hash': self.block_hash
        }

    def calc_blockhash(self):
        '''
        ブロックヘッダを構築し、ハッシュ化する
        '''

        blockheader = str(self.index) + str(self.prev_hash) + str(self.data) + \
            str(self.timestamp) + hex(self.bits)[2:] + str(self.nonce)
        h = hashlib.sha256(blockheader.encode()).hexdigest()
        self.block_hash = h
        return h

    def calc_target(self):
        '''
        ターゲットを算出
        '''

        # exponentを算出（24ビット右シフトし、3を引く）
        exponent_bytes = (self.bits >> 24) - 3
        # バイトをビットに変換
        exponent_bits = exponent_bytes * 8
        # coefficientを算出（論理積を取り、先頭2桁を排除）
        coefficient = self.bits & 0xffffff
        # exponent_bits分、左シフト
        return coefficient << exponent_bits

    def check_valid_hash(self):
        '''
        ハッシュ値がターゲットより小さいかどうか判定
        '''

        return int(self.calc_blockhash(), 16) <= self.calc_target()


class MerkleTree():
    '''
    マークルルートを定義
    '''

    def __init__(self):
        '''
        初期化
        '''

        self.tree_path = []
        # トランザクションデータを取得
        with open('./mempool.json') as f:
            mempool = json.load(f)
            tx_list = mempool['tx']
            c = random.randint(2, 30)
            # ランダムで要素を重複なしで30個取得
            txs_in_this_block = random.sample(tx_list, c)
            self.tree_path.append(txs_in_this_block)

    def sha256(self, data):
        '''
        ハッシュを算出
        '''

        return hashlib.sha256(data.encode()).hexdigest()

    def calc_merkleroot(self):
        '''
        マークルルートを算出
        '''

        txs = self.tree_path[0]
        # トランザクションデータが1つだけの場合
        if len(txs) == 1:
            return txs[0]
        # トランザクションデータを1つにまとめる
        while len(txs) > 1:
            # 配列要素が奇数の場合
            if len(txs) % 2 == 1:
                # 最後の要素をコピー
                txs.append(txs[-1])
            # ハッシュ値を計算
            hashes = []
            for i in range(0, len(txs), 2):
                hashes.append(self.sha256(''.join(txs[i:i+2])))
            txs = hashes
        return txs[0]


class Blockchain():
    '''
    全体の流れを制御
    '''

    def __init__(self, initial_bits):
        '''
        初期化
        '''

        self.chain = []
        self.initial_bits = initial_bits

    def add_block(self, block):
        '''
        ブロックにデータを追加
        '''

        self.chain.append(block)

    def getblockinfo(self, index=-1):
        '''
        chain配列の最後の要素を取り出し、JSON形式で出力
        '''

        # indent：インデントの大きさ、sort_keys：キーでソートを可能にする、ensure_ascii：日本語表記を可能にする
        return print(json.dumps(self.chain[index].to_json(), indent=2, sort_keys=True, ensure_ascii=False))

    def mining(self, block):
        '''
        マイニングを行う
        '''

        start_time = int(time.time() * 1000)
        while True:
            for n in range(MAX_32BIT + 1):
                block.nonce = n
                if block.check_valid_hash():
                    end_time = int(time.time() * 1000)
                    block.elapsed_time = str((end_time - start_time) / 1000.0) + '秒'
                    self.add_block(block)
                    self.getblockinfo()
                    return
            # タイムスタンプを調整
            new_time = datetime.datetime.now()
            if new_time == block.timestamp:
                block.timestamp += datetime.timedelta(seconds=1)
            else:
                block.timestamp = new_time

    def create_genesis(self):
        '''
        ジェネシスブロックを作成
        '''

        genesis_block = Block(0,
            '0000000000000000000000000000000000000000000000000000000000000000',
            'ジェネシスブロック', datetime.datetime.now(), self.initial_bits)
        self.mining(genesis_block)

    def add_newblock(self, i):
        '''
        新規ブロックを作成
        '''

        last_block = self.chain[-1]
        new_bits = self.get_retarget_bits()
        if new_bits < 0:
            bits = last_block.bits
        else:
            bits = new_bits
        # マークルルートを算出
        mt = MerkleTree()
        merkleroot = mt.calc_merkleroot()
        block = Block(i + 1, last_block.block_hash, merkleroot, datetime.datetime.now(), bits)
        self.mining(block)

    def get_retarget_bits(self):
        '''
        難易度調整（5ブロックごと）
        '''

        # 調整不要
        if len(self.chain) == 0 or len(self.chain) % 5 != 0:
            return -1
        # 140秒ごとにマイニングが成功することを目標とする
        expected_time = 140 * 5
        # 最初のブロックと最後のブロックを取り出す
        if len(self.chain) != 5:
            first_block = self.chain[-(1 + 5)]
        else:
            first_block = self.chain[0]
        last_block = self.chain[-1]
        # マイニングにかかった時間を算出
        first_time = first_block.timestamp.timestamp()
        last_time = last_block.timestamp.timestamp()
        total_time = last_time - first_time
        # 現在のターゲットを算出
        target = last_block.calc_target()
        # 比率を算出
        delta = total_time / expected_time
        if delta < 0.25:
            delta = 0.25
        if delta > 4:
            delta = 4
        new_target = int(target * delta)
        # exponentを算出
        exponent_bytes = (last_block.bits >> 24) - 3
        exponent_bits = exponent_bytes * 8
        # coefficientを算出
        temp_bits = new_target >> exponent_bits
        # 大きすぎていないか確認
        if temp_bits != temp_bits & 0xffffff:
            exponent_bytes += 1
            exponent_bits += 8
        # 小さすぎていないか確認
        elif temp_bits == temp_bits & 0xffff:
            exponent_bytes -= 1
            exponent_bits -= 8
        # exponentとcoefficientの論理和を取り、新しいターゲットを算出
        return ((exponent_bytes + 3) << 24) | (new_target >> exponent_bits)


if __name__ == '__main__':
    # Blockchainクラスをインスタンス化
    bc = Blockchain(INITIAL_BITS)
    # ジェネシスブロックを作成
    print('ジェネシスブロックを作成中・・・')
    bc.create_genesis()
    # 新規ブロックを作成
    for i in range(30):
        print(str(i + 2) + '番目のブロックを作成中・・・')
        bc.add_newblock(i)
