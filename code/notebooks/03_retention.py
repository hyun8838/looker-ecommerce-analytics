"""* 재구매 분석
* 지표 정의의 독립 재구현 없이 기존 함수 사용"""
from analysis import analyze_page

if __name__ == '__main__':
    result = analyze_page('retention')
    print(result['summary'].to_string())
    for figure in result['figures']:
        figure.show()
