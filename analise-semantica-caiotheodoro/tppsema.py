from myerror import MyError
from anytree import RenderTree, AsciiStyle
from anytree.exporter import DotExporter, UniqueDotExporter
from mytree import MyNode
from tppparser import retorna_arvore
import pandas as pd
import ply.yacc as yacc
import sys
import os
from utils import aux_simbolos_tabela, nodes, poda_arvore, processa_cabecalho, processa_lista_parametros, processa_tipo, tokens, processa_numero, processa_id, processa_parametro
from sys import argv, exit

import logging

logging.basicConfig(
    level=logging.DEBUG,
    filename="sema.log",
    filemode="w",
    format="%(filename)10s:%(lineno)4d:%(message)s"
)
log = logging.getLogger()

warr = []
aux_dict = {}
error_handler = MyError('SemaErrors')
escopo = 'global'
root = None
tipo = ''
nome_funcao = ''
tipo_retorno = ''
parametros = []
retorno = []
tipos = []
valor_atribuido = {}
valores = []
tipo_valor = []
dimensoes = 0
tam_dimensao_1 = 0
tam_dimensao_2 = 0


def atribuicao_expressao(expressao, valores):
    valores = valores

    for filho in expressao.children:
        if filho.label == 'numero':
            processa_numero(filho)
        elif filho.label == 'ID':
            processa_id(filho)

        valores = atribuicao_expressao(filho, valores)

    return valores


def encontra_indice_retorno(expressao):

    indice = ''
    tipo_retorno = ''

    for filho in expressao.children:
        if filho.label == 'numero':
            return processa_numero(filho)
        elif filho.label == 'ID':
            return processa_id(filho)

        tipo_retorno, indice = encontra_indice_retorno(filho)

    return tipo_retorno, indice


def encontra_atribuicao_valor(expressao, valores):
    tipo_retorno = ''
    valores = valores
    for filho in expressao.children:
        if filho.label == 'numero':
            processa_numero(filho)
        elif filho.label == 'ID':
            processa_id(filho)

        tipo_retorno, _ = encontra_indice_retorno(filho)

    return tipo_retorno, valores


def encontra_expressao_retorno(retorna, lista_retorno):

    for ret in retorna.children:
        if ret.label == 'ID':
            return processa_id(ret, aux_dict, lista_retorno)
        if ret.label == 'numero':
            return processa_numero(ret, aux_dict, lista_retorno)

        lista_retorno = encontra_expressao_retorno(ret, lista_retorno)

    return lista_retorno


def processa_expressao(ret):
    expressoes = ['expressao_aditiva', 'expressao_multiplicativa']
    if ret.label in expressoes:
        retorno = encontra_expressao_retorno(ret, retorno)
        return retorno
    encontra_valores_retorno(ret, retorno)


def encontra_valores_retorno(retorna, retorno):

    for ret in retorna.children:
        processa_expressao(ret)

    return retorno


def encontra_tipo_nome_parametro(parametro, tipo, nome):

    for param in parametro.children:
        tipo, nome = processa_parametro(param, tipo, nome)

    return tipo, nome


def encontra_parametro_funcao(no, parametros):

    parametros = parametros
    parametro = {}

    for n in no.children:
        if (no.label == 'parametro'):
            tipo, nome = encontra_tipo_nome_parametro(no, '', '')

            parametro[nome] = tipo

            parametros.append(parametro)

            return parametros
        encontra_parametro_funcao(n, parametros)

    return parametros


def encontra_parametros(no_parametro, parametros):
    no_parametro = no_parametro
    parametros = parametros
    parametro = {}
    tipo = ''
    nome = ''

    for no in no_parametro.children:
        if (no.label == 'expressao'):
            tipo, nome = encontra_indice_retorno(no)
            parametro[nome] = tipo
            parametros.append(parametro)

            return parametros

        encontra_parametros(no, parametros)
    return parametros


def verifica_dimensoes(tree, dimensao, indice_1, indice_2):
    def processa_indice(filho):
        if filho.children[0].label == 'indice':
            return 2, *encontra_indice_retorno(filho.children[0].children[1]), *encontra_indice_retorno(filho.children[2])
        else:
            return 1, *encontra_indice_retorno(filho.children[1]), 0

    indice_1 = indice_1
    indice_2 = indice_2
    dimensao = dimensao

    for filho in tree.children:
        if filho.label == 'indice':
            dimensao, indice_1, indice_2 = processa_indice(filho)
            return dimensao, indice_1, indice_2

        dimensao, indice_1, indice_2 = verifica_dimensoes(
            filho, dimensao, indice_1, indice_2)

    return dimensao, indice_1, indice_2


def processa_retorna(filho, tipo, nome_funcao, parametros):
    retorno_tipo_valor = encontra_valores_retorno(filho, 'n/a')
    linha_retorno = filho.label.split(':')[1]
    tipo_retorno = 'vazio'
    return tipo, nome_funcao, parametros, retorno_tipo_valor, tipo_retorno, linha_retorno


def encontra_dados_funcao(declaracao_funcao, tipo, nome_funcao, parametros, retorno_tipo_valor, tipo_retorno, linha_retorno):

    for filho in declaracao_funcao.children:
        if filho.label == 'tipo':
            tipo = processa_tipo(filho)
        elif filho.label == 'lista_parametros':
            parametros = processa_lista_parametros(filho)
        elif filho.label == 'cabecalho':
            nome_funcao, escopo = processa_cabecalho(filho, nome_funcao)
        elif 'retorna' in filho.label:
            return processa_retorna(filho, tipo, nome_funcao, parametros)
        tipo, nome_funcao, parametros, retorno_tipo_valor, tipo_retorno, linha_retorno = encontra_dados_funcao(
            filho, tipo, nome_funcao, parametros, retorno_tipo_valor, tipo_retorno, linha_retorno
        )

    return tipo, nome_funcao, parametros, retorno_tipo_valor, tipo_retorno, linha_retorno


def insere_tabela(tabela_simbolos, args):
    tabela_simbolos.loc[len(tabela_simbolos)] = args


def processa_declaracao_variaveis(filho, tabela_simbolos, dim):
    dim = verifica_dimensoes(filho, 0, 0, 0)

    # Descomentar isso depois
    global linha_declaracao
    linha_declaracao = filho.label.split(':')
    linha_declaracao = linha_declaracao[0] if len(
        linha_declaracao) == 1 else linha_declaracao[1]

    insere_tabela(tabela_simbolos,
                  [
                      'ID',
                      str(filho.children[2].children[0]
                          .children[0].children[0].label),
                      str(filho.children[0].children[0].children[0].label),
                      *dim,
                      escopo,
                      'N',
                      linha_declaracao,
                      'N',
                      'n/a',
                      'n/a'
                  ])

    return tabela_simbolos


def processa_declaracao_funcao(filho, tabela_simbolos):

    parametros = encontra_parametro_funcao(filho, parametros)
    linha_declaracao = filho.label.split(':')[1]

    tipo, nome_funcao, _, retorno, tipo_retorno, linha_retorno = encontra_dados_funcao(
        filho, '', '', '', '', '', '')

    tipo = tipo if tipo != '' else 'vazio'

    insere_tabela(tabela_simbolos, ['ID', nome_funcao, tipo, 0, 0,
                  0, escopo, 'N', linha_declaracao, 'S', parametros, 'n/a'])

    for p in parametros:
        for nome_param, tipo_param in p.items():
            insere_tabela(tabela_simbolos, [
                          'ID', nome_param, tipo_param, 0, 0, 0, escopo, 'S', linha_declaracao, 'N', 'n/a', 'n/a'])

    if retorno:
        muda_tipo_retorno_lista = []
        for ret in retorno:
            for nome_retorno, tipo_retorno in ret.items():
                tipo_retorno = tabela_simbolos.loc[tabela_simbolos['lex']
                                                   == nome_retorno]['tipo'].values
                tipo_variaveis_retorno = tipo_retorno[0] if len(
                    tipo_retorno) > 0 else 'vazio'

                muda_tipo_retorno = {nome_retorno: tipo_variaveis_retorno}
                muda_tipo_retorno_lista.append(muda_tipo_retorno)

                tipos.append(tipo_variaveis_retorno)

        tipo = 'flutuante' if 'flutuante' in tipos else 'inteiro'

        linha_dataframe = ['ID', 'retorna', tipo, 0, 0, 0, escopo,
                           'N', linha_retorno, 'S', 'n/a', muda_tipo_retorno_lista]
        tabela_simbolos.loc[len(tabela_simbolos)] = linha_dataframe


def retorna_funcao(tabela_simbolos):
    tipos = []

    # Check if there is already a 'retorna' row in the table for this function (i.e., with this scope)
    linha_retorno = tabela_simbolos.loc[(tabela_simbolos['lex'] == 'retorna') & (
        tabela_simbolos['escopo'] == escopo)]

    # Get the index of the row in the dataframe
    linha_retorno_index = linha_retorno.index[0]

    # Get the return values
    retorno_linha = linha_retorno['valor'].values.tolist()
    retorno = retorno_linha[0]

    if len(linha_retorno) > 0:
        pos = 0
        muda_tipo_retorno_lista = []
        global variavel_nao_declarada

        for ret in retorno:
            for nome_retorno, tipo_retorno in ret.items():
                # Search for the variables in the symbol table
                tipo_retorno = tabela_simbolos.loc[(tabela_simbolos['lex'] == nome_retorno) & (
                    tabela_simbolos['escopo'] == escopo)]

                tipo_variaveis_retorno = tipo_retorno['tipo'].values

                if len(tipo_variaveis_retorno) > 0:
                    tipo_variaveis_retorno = tipo_variaveis_retorno[0]
                else:
                    if nome_retorno not in variavel_nao_declarada:
                        print("Erro: Variável '%s' não declarada" %
                              nome_retorno)
                        variavel_nao_declarada.append(nome_retorno)
                    tipo_variaveis_retorno = 'vazio'

                muda_tipo_retorno = {nome_retorno: tipo_variaveis_retorno}
                muda_tipo_retorno_lista.append(muda_tipo_retorno)

                tipos.append(tipo_variaveis_retorno)
                pos += 1

        if len(tipos) > 0:
            tipo = 'flutuante' if 'flutuante' in tipos else 'inteiro'

        # Verify if there is actually a return value
        tabela_simbolos.at[linha_retorno_index,
                           'valor'] = muda_tipo_retorno_lista
        tabela_simbolos.at[linha_retorno_index, 'tipo'] = tipo


def chamada_funcao_aux(tabela_simbolos, filho):
    nome_funcao = ''
    parametros = []
    token = ''
    iniciacao = ''

    nome_funcao = filho.children[0].children[0].label
    parametros = encontra_parametros(filho, parametros)

    linha_declaracao = filho.label.split(':')[1]

    # Check if the function has a declaration
    declaracao_funcao = tabela_simbolos.loc[tabela_simbolos['lex']
                                            == nome_funcao]
    tipo_funcao = declaracao_funcao['tipo'].values[0] if len(
        declaracao_funcao) > 0 else 'vazio'

    parametro_list = []

    if len(parametros) >= 1:
        for param in parametros:
            for nome_param, tipo_param in param.items():
                parametro_dic = {}

                # Check if the parameter has been declared and initialized in the symbol table
                parametro_inicializado = tabela_simbolos.loc[(
                    tabela_simbolos['lex'] == nome_param) & (tabela_simbolos['iniciacao'] == 'S')]
                parametro_declarado = tabela_simbolos.loc[tabela_simbolos['lex'] == nome_param]

                parametro_dic[nome_param] = tipo_param
                parametro_list.append(parametro_dic)

                iniciacao = 'S' if len(parametro_inicializado) > 0 else 'N'

    # Create a row for the function call
    linha_dataframe = ['ID', filho.children[0].children[0].label, tipo_funcao, 0, 0, 0,
                       escopo, 'N', linha_declaracao, 'chamada_funcao', parametro_list, 'n/a']
    tabela_simbolos.loc[len(tabela_simbolos)] = linha_dataframe


def atribuicao_funcao_aux(tabela_simbolos, filho):
    tipo_valor = atribuicao_expressao(filho.children[2], 'n/a')
    variavel_atribuicao_nome = filho.children[0].children[0].children[0].label

    linha_declaracao = filho.label.split(':')[1]

    for i in tipo_valor:
        for valor, tipo in i.items():
            if tipo == 'parametro':
                variavel_declarada = tabela_simbolos.loc[(
                    tabela_simbolos['lex'] == valor) & (tabela_simbolos['iniciacao'] == 'N')]

                if len(variavel_declarada) > 0:
                    tipo = variavel_declarada['tipo'].values[0]
                elif len(variavel_declarada) == 0:
                    print("Erro: Variável '%s' não declarada" % valor)

            if tipo == 'NUM_INTEIRO':
                tipo = 'inteiro'
            elif tipo == 'NUM_PONTO_FLUTUANTE':
                tipo = 'flutuante'

            valor_atribuido[valor] = tipo
            valores.append(valor_atribuido)

            tipo_variavel_recebendo = tabela_simbolos.loc[(tabela_simbolos['lex'] == variavel_atribuicao_nome) & (
                tabela_simbolos['iniciacao'] == 'N') & (tabela_simbolos['escopo'] == escopo)]

            if tipo == 'ID':
                tipo_variavel_recebendo_global = tipo_variavel_recebendo
                tipo_variavel_recebendo = tipo_variavel_recebendo['tipo'].values

            if len(tipo_variavel_recebendo) > 0:
                tipo_variavel_recebendo = tipo_variavel_recebendo[0]

            if len(tipo_variavel_recebendo) == 0 and (tipo != 'inteiro' and tipo != 'flutuante'):
                tipo_variavel_recebendo_global = tabela_simbolos.loc[(
                    tabela_simbolos['lex'] == variavel_atribuicao_nome) & (tabela_simbolos['iniciacao'] == 'N')]

                if len(tipo_variavel_recebendo_global) > 0:
                    tipo_variavel_recebendo_global = tipo_variavel_recebendo_global['tipo'].values
                    tipo_variavel_recebendo_global = tipo_variavel_recebendo_global[0]
                    tipo_variavel_recebendo = tipo_variavel_recebendo_global

            else:
                tipo_variavel_valor = tipo
                tipo_variavel_recebendo = tipo_variavel_valor

            dimensoes = tabela_simbolos.loc[(tabela_simbolos['lex'] == variavel_atribuicao_nome) & (
                tabela_simbolos['iniciacao'] == 'N')]
            tam_dimensao_1 = tabela_simbolos.loc[(tabela_simbolos['lex'] == variavel_atribuicao_nome) & (
                tabela_simbolos['iniciacao'] == 'N')]
            tam_dimensao_2 = tabela_simbolos.loc[(tabela_simbolos['lex'] == variavel_atribuicao_nome) & (
                tabela_simbolos['iniciacao'] == 'N')]

            dimensoes = dimensoes['dimensao'].values

            if len(dimensoes) > 0:
                dimensoes = dimensoes[0]
            else:
                dimensoes = 0

            tam_dimensao_1 = tam_dimensao_1['tam_dim1'].values

            if len(tam_dimensao_1) > 0:
                tam_dimensao_1 = tam_dimensao_1[0]

            tam_dimensao_2 = tam_dimensao_2['tam_dim2'].values

            if len(tam_dimensao_2) > 0:
                tam_dimensao_2 = tam_dimensao_2[0]

            if int(dimensoes) > 0:
                dimensoes, tam_dimensao_1, tam_dimensao_2 = verifica_dimensoes(
                    filho, 0, 0, 0)

            linha_dataframe = ['ID', variavel_atribuicao_nome, tipo_variavel_recebendo, dimensoes,
                               tam_dimensao_1, tam_dimensao_2, escopo, 'S', linha_declaracao, 'N', 'n/a', valores]
            tabela_simbolos.loc[len(tabela_simbolos)] = linha_dataframe


def monta_tabela_simbolos(tree, tabela_simbolos):

    dim = [0, '', '']

    for filho in tree.children:
        if ('declaracao_variaveis' in filho.label):
            return processa_declaracao_variaveis(filho, tabela_simbolos, dim)
        elif ('declaracao_funcao' in filho.label):
            processa_declaracao_funcao(filho, tabela_simbolos)

        elif ('retorna' in filho.label):
            retorna_funcao(tabela_simbolos)

        elif ('chamada_funcao' in filho.label):
            chamada_funcao_aux(tabela_simbolos, filho)
        elif ('atribuicao' in filho.label):
            atribuicao_funcao_aux(tabela_simbolos, filho)

        monta_tabela_simbolos(filho, tabela_simbolos)

    return tabela_simbolos


def verifica_tipo_atribuicao(variavel_atual, tipo_variavel, escopo_variavel, inicializacao_variaveis, variaveis, funcoes, tabela_simbolos):
    # Vou verificar se a variável atual é do mesmo tipo da sua atribuição
    status = True
    tipo_atribuicao = ''
    nome_inicializacao = ''
    tipo_variavel_inicializacao_retorno = ''
    tipo_variavel_novo = ''
    tipos_distintos = []

    # Nome da variável que está recebendo um valor
    nome_variavel = variavel_atual['lex']
    for ini_variaveis in inicializacao_variaveis:
        for ini_var in ini_variaveis:
            for nome_variavel_inicializacao, tipo_variavel_inicializacao in ini_var.items():

                status = True
                nome_inicializacao = nome_variavel_inicializacao
                # Pegar a declaração da variável que está recebendo um valor no escopo
                # Caso não encontre, procurar no escopo global
                declaracao_variavel = tabela_simbolos.loc[(tabela_simbolos['lex'] == nome_variavel) & (
                    tabela_simbolos['escopo'] == escopo_variavel) & (tabela_simbolos['iniciacao'] == 'N')]

                if len(declaracao_variavel) == 0:
                    declaracao_variavel_global = tabela_simbolos.loc[(tabela_simbolos['lex'] == nome_variavel) & (
                        tabela_simbolos['escopo'] == 'global') & (tabela_simbolos['iniciacao'] == 'N')]

                    if len(declaracao_variavel_global) > 0:
                        tipo_variavel_novo = declaracao_variavel_global['tipo'].values[0]
                else:
                    tipo_variavel_novo = declaracao_variavel['tipo'].values[0]

                # Verificar se ela pertence ás funções ou ás variáveis
                if nome_variavel_inicializacao in funcoes:
                    tipo_atribuicao = tabela_simbolos.loc[tabela_simbolos['lex']
                                                          == nome_variavel_inicializacao]
                    tipo_atribuicao = tipo_atribuicao['tipo'].values
                    tipo_atribuicao = tipo_atribuicao[0]

                    if tipo_variavel_novo == tipo_atribuicao:
                        status = True
                    else:
                        status = False

                    if status == False:
                        aviso_string = "Aviso: Atribuição de tipos distintos '%s' %s e '%s' %s" % (
                            nome_variavel, tipo_variavel_novo, nome_variavel_inicializacao, tipo_variavel_inicializacao)
                        if aviso_string not in warr:
                            warr.append(aviso_string)
                            print("Aviso: Atribuição de tipos distintos '%s' %s e '%s' %s" % (
                                nome_variavel, tipo_variavel_novo, nome_variavel_inicializacao, tipo_variavel_inicializacao))

                    return status, tipo_variavel_inicializacao, tipo_variavel_novo, nome_inicializacao

                elif nome_variavel_inicializacao in variaveis['lex'].values:
                    tipo_atribuicao = tabela_simbolos.loc[(tabela_simbolos['lex'] == nome_variavel_inicializacao) & (
                        tabela_simbolos['escopo'] == escopo_variavel) & (tabela_simbolos['iniciacao'] == 'N')]

                    if len(tipo_atribuicao) == 0:
                        tipo_atribuicao = tabela_simbolos.loc[(tabela_simbolos['lex'] == nome_variavel_inicializacao) & (
                            tabela_simbolos['escopo'] == 'global') & (tabela_simbolos['iniciacao'] == 'N')]

                    tipo_atribuicao = tipo_atribuicao['tipo'].values
                    if len(tipo_atribuicao) > 0:
                        tipo_atribuicao = tipo_atribuicao[0]

                    if len(tipo_variavel_novo) > 0 and len(tipo_atribuicao) > 0:
                        if tipo_variavel_novo == tipo_atribuicao:
                            status = True
                        else:
                            status = False

                    if status == False:
                        aviso_variavel_string = "Aviso: Atribuição de tipos distintos '%s' %s e '%s' %s" % (
                            nome_variavel, tipo_variavel_novo, nome_variavel_inicializacao, tipo_variavel_inicializacao)
                        if aviso_variavel_string not in warr:
                            warr.append(aviso_variavel_string)
                            print("Aviso: Atribuição de tipos distintos '%s' %s e '%s' %s" % (
                                nome_variavel, tipo_variavel_novo, nome_variavel_inicializacao, tipo_variavel_inicializacao))

                # Significa que é um digito
                elif tipo_variavel_inicializacao == 'inteiro' or tipo_variavel_inicializacao == 'flutuante':

                    declaracao_variavel_valor = tabela_simbolos.loc[(tabela_simbolos['lex'] == nome_variavel) & (
                        tabela_simbolos['escopo'] == escopo_variavel) & (tabela_simbolos['iniciacao'] == 'N')]

                    if len(declaracao_variavel_valor) == 0:
                        declaracao_variavel_global_valor = tabela_simbolos.loc[(tabela_simbolos['lex'] == nome_variavel) & (
                            tabela_simbolos['escopo'] == 'global') & (tabela_simbolos['iniciacao'] == 'N')]

                        if len(declaracao_variavel_global_valor) > 0:
                            tipo_variavel_novo = declaracao_variavel_global_valor['tipo'].values[0]
                    else:
                        tipo_variavel_novo = declaracao_variavel['tipo'].values[0]

                    if '.' in str(nome_variavel_inicializacao):
                        tipo_variavel = 'flutuante'

                    if tipo_variavel_inicializacao == 'flutuante':
                        if tipo_variavel == 'flutuante':
                            status = True
                            tipo_variavel_novo = 'flutuante'
                        else:
                            status = False
                            tipo_variavel_novo = 'inteiro'

                    else:
                        if tipo_variavel_novo == 'inteiro':
                            status = True
                            tipo_variavel_novo = 'inteiro'
                        else:
                            status = False
                            tipo_variavel_novo = 'flutuante'

                    if status == False:
                        aviso_variavel_string = "Aviso: Atribuição de tipos distintos '%s' %s e '%s' %s" % (
                            nome_variavel, tipo_variavel_novo, nome_variavel_inicializacao, tipo_variavel_inicializacao)

                        if aviso_variavel_string not in warr:
                            warr.append(aviso_variavel_string)
                            print("Aviso: Atribuição de tipos distintos '%s' %s e '%s' %s" % (
                                nome_variavel, tipo_variavel_novo, nome_variavel_inicializacao, tipo_variavel_inicializacao))

                tipo_variavel_inicializacao_retorno = tipo_variavel_inicializacao

    return status, tipo_variavel_inicializacao_retorno, tipo_variavel_novo, nome_inicializacao


def verifica_regras_semanticas(tabela_simbolos):
    # pegar só as variáveis
    variaveis = tabela_simbolos.loc[tabela_simbolos['funcao'] == 'N']

    funcoes = tabela_simbolos.loc[tabela_simbolos['funcao'] != 'N']
    funcoes = funcoes['lex'].unique()

    i = 0

    # Valores únicos das variáveis declaradas e inicializadas
    variaveis_repetidas_valores_inicio = variaveis['lex'].unique()
    var_verificacao = variaveis
    # Retira as repetidas
    for var in variaveis_repetidas_valores_inicio:

        linhas = tabela_simbolos[tabela_simbolos['lex'] == var].index.tolist()
        linha = tabela_simbolos[tabela_simbolos['lex'] == var]

        if len(linhas) > 1:
            linhas = linha[linha['iniciacao'] == 'N'].index.tolist()
            if len(linhas) > 1:
                var_verificacao.drop(linhas[0])

    # dropar as declarações
    for index, row in variaveis.iterrows():
        lista_declaracao_variavel = tabela_simbolos.loc[(tabela_simbolos['lex'] == row['lex']) & (
            tabela_simbolos['iniciacao'] == 'N') & (tabela_simbolos['escopo'] == row['escopo'])]

        if len(lista_declaracao_variavel) > 1:
            string_variavel_declarada = "Aviso: Variável '%s' já declarada anteriormente" % row[
                'lex']
            if string_variavel_declarada not in warr:
                warr.append(string_variavel_declarada)
                print("Aviso: Variável '%s' já declarada anteriormente" %
                      row['lex'])

    # Se ainda tiver alguma variável do mesmo escopo
    escopo_variaveis_verificacao = var_verificacao['escopo'].unique()
    for e in escopo_variaveis_verificacao:
        for var in variaveis_repetidas_valores_inicio:
            mesmo_escopo = var_verificacao[(var_verificacao['escopo'] == e) & (
                var_verificacao['lex'] == var)]

            if len(mesmo_escopo) > 1:
                linha_mesmo_escopo = mesmo_escopo.index.tolist()
                var_verificacao.drop(linha_mesmo_escopo[0])

    for linha in var_verificacao.index:
        inicializacao_variaveis = tabela_simbolos.loc[(tabela_simbolos['lex'] == variaveis['lex'][linha]) & (
            tabela_simbolos['escopo'] == variaveis['escopo'][linha]) & (tabela_simbolos['iniciacao'] == 'S')]
        inicializacao_variaveis = inicializacao_variaveis['valor'].values

        inicializacao_variaveis_valores = []
        if len(inicializacao_variaveis) > 0:
            inicializacao_variaveis_valores = inicializacao_variaveis

        # Depois de pegar o valor é necessário verificar se é uma variável ou uma função
        # Fazer uma função que retorna o tipo do valor atribuído
        if len(inicializacao_variaveis_valores) > 0:
            boolen_tipo_igual, tipo_variavel_atribuida, tipo_atribuicao, nome_variavel_inicializacao = verifica_tipo_atribuicao(
                variaveis.iloc[i], variaveis['tipo'][linha], variaveis['escopo'][linha], inicializacao_variaveis_valores, variaveis, funcoes, tabela_simbolos)

        i += 1

    # # Valores únicos das variáveis declaradas e inicializadas
    variaveis_repetidas_valores = variaveis['lex'].unique()

    for var_rep in variaveis_repetidas_valores:
        variaveis_repetidas = variaveis.loc[variaveis['lex'] == var_rep]

        if len(variaveis_repetidas) > 1:
            variaveis_repetidas_index = variaveis_repetidas[variaveis_repetidas['iniciacao'] == 'N'].index
            variaveis_repetidas_linhas = variaveis_repetidas[variaveis_repetidas['iniciacao'] == 'N']
            # print("VARIAVEIS REPETIDAS")
            # print(variaveis_repetidas_linhas)
            # Checar se elas são do mesmo escopo
            # Pego os escopos
            escopos_variaveis = variaveis_repetidas_linhas['escopo'].unique()

            # Passo por todas os escopos
            for esc in escopos_variaveis:
                variaveis_repetidas_escopo_igual_index = variaveis_repetidas_linhas.loc[
                    variaveis_repetidas_linhas['escopo'] == esc].index
                variaveis.drop(variaveis_repetidas_escopo_igual_index[0])

        elif len(variaveis_repetidas) == 0:
            print("Erro: Variável '%s' não declarada" % var_rep)

    # retirar os repetidos novamente se houver
    repetidos_variaveis_atribuicao = variaveis['lex'].unique()
    for rep in repetidos_variaveis_atribuicao:
        tabela_variaveis_repetida = variaveis.loc[variaveis['lex'] == rep]
        tabela_variaveis_repetida_index = variaveis.loc[variaveis['lex'] == rep].index

        if len(tabela_variaveis_repetida_index) > 1:
            variaveis.drop(tabela_variaveis_repetida_index[0])

    # Verifica se existe a função principal
    if ('principal' not in funcoes):
        print('Erro: Função principal não declarada')

    for index, row in variaveis.iterrows():
        dimensao_variavel = row['dimensao']

        if int(dimensao_variavel) > 0:
            if int(dimensao_variavel) == 1:
                # Verifica se a dimensão tem um '.'
                if '.' in str(row['tam_dim1']):
                    aviso_indice = "Erro: índice de array '%s' não inteiro" % row['lex']
                    if aviso_indice not in warr:
                        warr.append(aviso_indice)
                        print("Erro: índice de array '%s' não inteiro" %
                              row['lex'])

            # Verifica se tem mais de uma dimensão
            elif int(dimensao_variavel) == 2:
                # Verifica se a dimensão tem um '.'
                if '.' in str(row['tam_dim2']):
                    print("Erro: índice de array '%s' não inteiro" %
                          row['lex'])

        inicializada = False

        df = tabela_simbolos.loc[tabela_simbolos['lex'] == row['lex']]

        # Caso tenha mais de uma linha com o mesmo valor na coluna lex
        if (len(df) > 1):
            for lin in range(len(df)):
                if (df.iloc[lin]['iniciacao'] != 'N'):
                    inicializada = True
        else:
            if (tabela_simbolos.iloc[0]['iniciacao'] != 'N'):
                inicializada = True

        # Procura nos retornos onde o escopo é diferente de principal
        # E vê se está no retorno
        retorna_parametros = tabela_simbolos.loc[(tabela_simbolos['lex'] == 'retorna') & (
            tabela_simbolos['escopo'] == row['escopo'])]
        retorna_parametros = retorna_parametros['valor']
        retorna_parametros = retorna_parametros.values

        # Caso tenha algum retorno que esteja no mesmo escopo que a declaração da variável
        if len(retorna_parametros) > 0:
            # Só verifica se a variável está nos parâmetros do retorno
            for retornos_variaveis in retorna_parametros:
                for rt_vs in retornos_variaveis:
                    for nome_variavel_retorno, tipo_variavel_retorno in rt_vs.items():

                        if (row['lex'] == nome_variavel_retorno):
                            inicializada = True

        if (inicializada == False):
            string_declarada_nao_utilizada = "Aviso: Variável '%s' declarada e não utilizada" % row[
                'lex']
            if string_declarada_nao_utilizada not in warr:
                warr.append(string_declarada_nao_utilizada)
                print("Aviso: Variável '%s' declarada e não utilizada" %
                      row['lex'])

    # Verifica todas as funções/chamadas de funções
    for func in funcoes:
        if func == 'principal':
            # Caso o lex seja principal verificar se há um retorno e o tipo dele
            tabela_retorno = tabela_simbolos.loc[tabela_simbolos['lex'] == 'retorno']

            if (tabela_retorno.shape[0] == 0):
                print(
                    "Erro: Função principal deveria retornar inteiro, mas retorna vazio")

            # Verificar se a função principal chama ela mesma
            chamada_funcao_principal = tabela_simbolos.loc[(
                tabela_simbolos['funcao'] == 'chamada_funcao') & (tabela_simbolos['lex'] == 'principal')]

            if len(chamada_funcao_principal) > 0:
                verifica_escopo = chamada_funcao_principal['escopo'].values[0]

                if verifica_escopo == 'principal':
                    print("Aviso: Chamada recursiva para principal")
                else:
                    print("Erro: Chamada para a função principal não permitida")
        else:
            # Verificar se há uma chamada de função
            chamada_funcao = tabela_simbolos.loc[(tabela_simbolos['lex'] == func) & (
                tabela_simbolos['funcao'] == 'chamada_funcao')]
            declaracao_funcao = tabela_simbolos.loc[(
                tabela_simbolos['lex'] == func) & (tabela_simbolos['funcao'] == 'S')]

            # Verifica se o tipo da função é do mesmo tipo do retorno
            if (func == 'retorna'):
                escopo_retorno = declaracao_funcao['escopo'].values
                escopo_retorno = escopo_retorno[0]

                # Pego a variável retornada
                variavel_retornada = declaracao_funcao['valor'].values[0]
                for var in variavel_retornada:
                    for n, t in var.items():
                        variavel_retornada = n

                # Atribuo o valor do tipo da funçao
                tipo_retorno_funcao = declaracao_funcao['tipo'].values
                tipo_retorno_funcao = tipo_retorno_funcao[0]

                if variavel_retornada in tabela_simbolos['lex'].unique():
                    declaracao_variavel = tabela_simbolos.loc[(tabela_simbolos['lex'] == variavel_retornada) & (
                        tabela_simbolos['escopo'] == escopo_retorno) & (tabela_simbolos['iniciacao'] == 'N')]

                    if len(declaracao_variavel) == 0:

                        declaracao_variavel_global = tabela_simbolos.loc[(tabela_simbolos['lex'] == variavel_retornada) & (
                            tabela_simbolos['escopo'] == 'global') & (tabela_simbolos['iniciacao'] == 'N')]

                        if len(declaracao_variavel_global) == 0:
                            declaracao_variavel_global = tabela_simbolos.loc[(tabela_simbolos['lex'] == variavel_retornada) & (
                                tabela_simbolos['escopo'] == escopo_retorno) & (tabela_simbolos['iniciacao'] == 'S')]

                        tipo_retorno_funcao = declaracao_variavel_global['tipo'].values[0]

                procura_funcao_escopo = tabela_simbolos.loc[(tabela_simbolos['funcao'] == 'S') & (
                    tabela_simbolos['escopo'] == escopo_retorno) & (tabela_simbolos['lex'] != 'retorna')]

                nome_funcao = procura_funcao_escopo['lex'].values
                nome_funcao = nome_funcao[0]

                tipo_funcao = procura_funcao_escopo['tipo'].values
                tipo_funcao = tipo_funcao[0]

                if (tipo_funcao != tipo_retorno_funcao):
                    print("Erro: Função '%s' do tipo %s retornando %s" %
                          (nome_funcao, tipo_funcao, tipo_retorno_funcao))

            # Verifica se há alguma chamada de função
            if len(chamada_funcao) > 0:

                # Se há uma declaração
                if len(declaracao_funcao) < 1:
                    print("Erro: Chamada a função '%s' que não foi declarada" % func)
                else:
                    # Agora verifico a quantidade de parâmetro
                    quantidade_parametros_chamada = chamada_funcao['parametros']
                    quantidade_parametros_chamada = quantidade_parametros_chamada.values
                    quantidade_parametros_chamada = quantidade_parametros_chamada[0]

                    quantidade_parametros_declaracao_funcao = declaracao_funcao['parametros']
                    quantidade_parametros_declaracao_funcao = quantidade_parametros_declaracao_funcao.values
                    quantidade_parametros_declaracao_funcao = quantidade_parametros_declaracao_funcao[
                        0]

                    if len(quantidade_parametros_chamada) < len(quantidade_parametros_declaracao_funcao):
                        print(
                            "Erro: Chamada à função '%s' com número de parâmetros menor que o declarado" % func)

                    elif len(quantidade_parametros_chamada) > len(quantidade_parametros_declaracao_funcao):
                        print(
                            "Erro: Chamada à função '%s' com número de parâmetros maior que o declarado" % func)

            else:
                # Caso não tenha nenhuma chamada, porém ainda houve uma declaração
                if len(declaracao_funcao) > 0:
                    if func != 'retorna':
                        print(
                            "Aviso: Função '%s' declarada, mas não utilizada" % func)


# Programa Principal.
if __name__ == "__main__":
    if(len(sys.argv) < 2):
        raise TypeError(error_handler.newError('ERR-SEM-USE'))

    aux = argv[1].split('.')
    if aux[-1] != 'tpp':
        raise IOError(error_handler.newError('ERR-SEM-NOT-TPP'))
    elif not os.path.exists(argv[1]):
        raise IOError(error_handler.newError('ERR-SEM-FILE-NOT-EXISTS'))
    else:
        data = open(argv[1])
        source_file = data.read()
        root = retorna_arvore(source_file)

        if root:
            tab_sym = aux_simbolos_tabela()
            tab_sym = monta_tabela_simbolos(root, tab_sym)

            verifica_regras_semanticas(tab_sym)

            tab_sym.to_csv(f'{argv[1]}.csv', index=None, header=True)
            poda_arvore(root, tokens, nodes)
            UniqueDotExporter(root).to_picture(
                f'{sys.argv[1]}.podada.unique.ast.png')
