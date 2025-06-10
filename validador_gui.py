import sys
import os
import traceback
import logging
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QPushButton, QFileDialog, QLabel, QLineEdit,
    QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QProgressDialog,
    QTabWidget, QComboBox, QMessageBox, QSpacerItem, QSizePolicy, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal

def setup_logging():
    """Configura o logger para salvar erros em um arquivo."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename='app_log.txt',
        filemode='w'
    )
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logging.critical("Erro não tratado que encerrou a aplicação:", exc_info=(exc_type, exc_value, exc_traceback))
    sys.excepthook = handle_exception

try:
    from validador_csv import (
        validar_csv, salvar_csv_processado, detectar_delimitador_e_encoding,
        EXPECTED_HEADER
    )
except ImportError as e:
    setup_logging()
    logging.critical(f"Falha ao importar 'validador_csv.py': {e}")
    QMessageBox.critical(None, "Erro Crítico", f"Não foi possível encontrar o arquivo 'validador_csv.py'.\nO programa será encerrado. Verifique o log 'app_log.txt'.\n\nErro: {e}")
    sys.exit(1)

class ValidationWorker(QObject):
    """Worker que executa a validação do CSV em uma thread separada para não travar a UI."""
    finished = pyqtSignal(tuple)
    error = pyqtSignal(str)

    def __init__(self, file_path, header_map, usar_api):
        super().__init__()
        self.file_path = file_path
        self.header_map = header_map
        self.usar_api = usar_api

    def run(self):
        """Executa a validação e emite o sinal 'finished'."""
        try:
            logging.info(f"Iniciando validação para o arquivo: {self.file_path}. Uso de API: {self.usar_api}")
            results = validar_csv(self.file_path, header_map=self.header_map, usar_api=self.usar_api)
            self.finished.emit(results)
            logging.info("Validação concluída com sucesso na thread.")
        except Exception as e:
            error_details = f"Erro na thread de validação: {e}\n{traceback.format_exc()}"
            logging.error(error_details)
            self.error.emit(error_details)

class ValidadorCSVApp(QWidget):
    """Classe principal que define a interface gráfica da aplicação."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Validador e Corretor de Arquivo CSV - PortalPostal")
        self.setGeometry(100, 100, 950, 750)
        
        self.dados_com_todas_correcoes = []
        self.dados_apenas_formato = []
        self.correcoes_sugeridas = []
        self.current_file_header = []
        self.validation_thread = None
        self.validation_worker = None
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Arquivo CSV:"))
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        file_layout.addWidget(self.file_path_edit)
        browse_button = QPushButton("Procurar...")
        browse_button.clicked.connect(self.browse_file)
        file_layout.addWidget(browse_button)
        main_layout.addLayout(file_layout)

        self.header_mapping_group = QWidget()
        group_layout = QVBoxLayout(self.header_mapping_group)
        group_layout.addWidget(QLabel("<b>Mapeamento de Cabeçalho (Opcional):</b>"))
        self.scroll_area_mapping = QScrollArea()
        self.scroll_area_mapping.setWidgetResizable(True)
        self.mapping_widget_container = QWidget()
        self.header_mapping_layout = QGridLayout(self.mapping_widget_container)
        self.scroll_area_mapping.setWidget(self.mapping_widget_container)
        group_layout.addWidget(self.scroll_area_mapping)
        self.header_mapping_group.setVisible(False)
        main_layout.addWidget(self.header_mapping_group)

        self.api_checkbox = QCheckBox("Consultar API de CEP para validar endereços (processo mais lento)")
        self.api_checkbox.setChecked(True)
        self.api_checkbox.setStyleSheet("QCheckBox { margin-top: 10px; }")
        main_layout.addWidget(self.api_checkbox)

        action_layout = QHBoxLayout()
        self.validate_button = QPushButton("Validar Arquivo Selecionado")
        self.validate_button.clicked.connect(self.run_validation)
        action_layout.addWidget(self.validate_button)
        
        self.clear_button = QPushButton("Limpar")
        self.clear_button.clicked.connect(self.clear_interface)
        action_layout.addWidget(self.clear_button)

        self.save_button = QPushButton("Salvar Arquivo...")
        self.save_button.clicked.connect(self.confirmar_e_salvar_csv)
        self.save_button.setEnabled(False)
        action_layout.addWidget(self.save_button)
        main_layout.addLayout(action_layout)
        
        self.results_tabs = QTabWidget()
        self.line_errors_table = QTableWidget(0, 3)
        self.line_errors_table.setHorizontalHeaderLabels(["Linha", "Coluna", "Mensagem"])
        self.line_errors_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.results_tabs.addTab(self.line_errors_table, "Erros e Avisos")

        self.corrections_table = QTableWidget(0, 5)
        self.corrections_table.setHorizontalHeaderLabels(["Linha", "Coluna", "Original", "Corrigido", "Fonte"])
        self.corrections_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.results_tabs.addTab(self.corrections_table, "Correções Sugeridas")
        main_layout.addWidget(self.results_tabs)
        
        self.status_label = QLabel("Pronto. Selecione um arquivo para começar.")
        main_layout.addWidget(self.status_label)
        self.setLayout(main_layout)

    def clear_interface(self):
        logging.info("Interface limpa pelo usuário.")
        self.file_path_edit.clear()
        self.line_errors_table.setRowCount(0)
        self.corrections_table.setRowCount(0)
        self.save_button.setEnabled(False)
        self.dados_com_todas_correcoes = []
        self.dados_apenas_formato = []
        self.correcoes_sugeridas = []
        self.current_file_header = []
        self.header_mapping_group.setVisible(False)
        self.status_label.setText("Pronto. Selecione um arquivo para começar.")
        while self.header_mapping_layout.count():
            child = self.header_mapping_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

    def browse_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo CSV", "", "Arquivos CSV (*.csv)")
        if file_name:
            self.clear_interface()
            self.file_path_edit.setText(file_name)
            logging.info(f"Arquivo selecionado: {file_name}")
            self.populate_header_mapping_ui(file_name)

    def populate_header_mapping_ui(self, file_path):
        while self.header_mapping_layout.count():
            child = self.header_mapping_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            
        header, _, _, message = detectar_delimitador_e_encoding(file_path)
        if not header:
            QMessageBox.critical(self, "Erro ao Ler Arquivo", message)
            self.status_label.setText(f"Falha ao ler o arquivo: {message}")
            logging.error(f"Falha ao ler cabeçalho: {message}")
            return
        
        self.status_label.setText(f"Arquivo '{os.path.basename(file_path)}' carregado. {message or ''}")
        logging.info(f"Cabeçalho lido com sucesso. Detalhes: {message}")
        self.current_file_header = header
        self.header_mapping_group.setVisible(True)
        self.header_map_combos = []
        self.header_mapping_layout.addWidget(QLabel("<b>Coluna do Arquivo</b>"), 0, 0)
        self.header_mapping_layout.addWidget(QLabel("<b>Mapear para Coluna do Sistema</b>"), 0, 1)
        for i, col_name in enumerate(self.current_file_header):
            label = QLabel(col_name.strip())
            combo = QComboBox()
            combo.addItem("")
            combo.addItems(EXPECTED_HEADER)
            normalized_col = col_name.strip().upper()
            matching_header = next((h for h in EXPECTED_HEADER if h.upper() == normalized_col), None)
            if matching_header:
                combo.setCurrentText(matching_header)
            self.header_mapping_layout.addWidget(label, i + 1, 0)
            self.header_mapping_layout.addWidget(combo, i + 1, 1)
            self.header_map_combos.append(combo)
        self.header_mapping_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding), len(header) + 1, 0)

    def run_validation(self):
        file_path = self.file_path_edit.text()
        if not file_path:
            QMessageBox.warning(self, "Atenção", "Por favor, selecione um arquivo CSV primeiro.")
            return
        user_header_map = {
            col.strip(): self.header_map_combos[i].currentText()
            for i, col in enumerate(self.current_file_header)
            if self.header_map_combos[i].currentText()
        } if self.header_mapping_group.isVisible() else None

        self.validate_button.setEnabled(False)
        self.save_button.setEnabled(False)
        usar_api = self.api_checkbox.isChecked()
        dialog_text = "Validando arquivo..."
        if usar_api: dialog_text += "\nAs consultas de CEP podem levar alguns minutos."

        self.progress_dialog = QProgressDialog(dialog_text, "Cancelar", 0, 0, self)
        self.progress_dialog.setWindowTitle("Processando")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.show()

        self.validation_thread = QThread()
        self.validation_worker = ValidationWorker(file_path, user_header_map, usar_api)
        self.validation_worker.moveToThread(self.validation_thread)
        self.validation_thread.started.connect(self.validation_worker.run)
        self.validation_worker.finished.connect(self.handle_validation_results)
        self.validation_worker.error.connect(self.handle_validation_error)
        self.validation_thread.start()

    def handle_validation_results(self, results):
        self.progress_dialog.close()
        erros_criticos, avisos, erros_linha, self.correcoes_sugeridas, self.dados_apenas_formato, self.dados_com_todas_correcoes = results
        self._populate_results_ui(erros_criticos, avisos, erros_linha, self.correcoes_sugeridas)
        if not erros_criticos and (self.dados_apenas_formato and len(self.dados_apenas_formato) > 1):
            self.save_button.setEnabled(True)
        self.on_validation_thread_finished()

    def handle_validation_error(self, error_message):
        self.progress_dialog.close()
        QMessageBox.critical(self, "Erro de Validação", f"Ocorreu um erro inesperado:\n{error_message}")
        self.status_label.setText("Erro inesperado durante a validação.")
        self.on_validation_thread_finished()

    def on_validation_thread_finished(self):
        self.validate_button.setEnabled(True)
        if self.validation_thread:
            self.validation_thread.quit()
            self.validation_thread.wait()
        self.validation_thread = None
        self.validation_worker = None

    def _populate_results_ui(self, erros_criticos, avisos, erros_linha, correcoes):
        combined_errors_warnings = []
        for e in erros_criticos:
            combined_errors_warnings.append({'linha': 'Global', 'coluna': 'Crítico', 'mensagem': e, 'is_warning': False})
        for a in avisos:
            combined_errors_warnings.append({'linha': 'Global', 'coluna': 'Aviso', 'mensagem': a, 'is_warning': True})
        for e in erros_linha:
            e['is_warning'] = False
            combined_errors_warnings.append(e)
        
        self.line_errors_table.setRowCount(0)
        self.line_errors_table.setRowCount(len(combined_errors_warnings))
        for i, item in enumerate(combined_errors_warnings):
            self.line_errors_table.setItem(i, 0, QTableWidgetItem(str(item.get('linha', ''))))
            self.line_errors_table.setItem(i, 1, QTableWidgetItem(str(item.get('coluna', ''))))
            self.line_errors_table.setItem(i, 2, QTableWidgetItem(str(item.get('mensagem', ''))))
            if item.get('is_warning'):
                for j in range(3): self.line_errors_table.item(i, j).setForeground(Qt.GlobalColor.darkYellow)
        
        self.corrections_table.setRowCount(0)
        self.corrections_table.setRowCount(len(correcoes))
        for i, cor in enumerate(correcoes):
            self.corrections_table.setItem(i, 0, QTableWidgetItem(str(cor.get('linha', ''))))
            self.corrections_table.setItem(i, 1, QTableWidgetItem(str(cor.get('coluna', ''))))
            self.corrections_table.setItem(i, 2, QTableWidgetItem(str(cor.get('original', ''))))
            self.corrections_table.setItem(i, 3, QTableWidgetItem(str(cor.get('corrigido', ''))))
            self.corrections_table.setItem(i, 4, QTableWidgetItem(str(cor.get('fonte', 'Formato'))))
        
        if erros_criticos or erros_linha: self.results_tabs.setCurrentWidget(self.line_errors_table)
        elif correcoes: self.results_tabs.setCurrentWidget(self.corrections_table)

        status = "Validação concluída."
        if erros_criticos: status += f" {len(erros_criticos)} erro(s) crítico(s)."
        elif erros_linha: status += f" {len(erros_linha)} erro(s) de linha."
        else: status = "Validação concluída com sucesso!"
        self.status_label.setText(status)

    def confirmar_e_salvar_csv(self):
        if not self.dados_com_todas_correcoes:
            QMessageBox.information(self, "Informação", "Não há dados processados para salvar.")
            return

        ha_correcoes_api = any(c.get('fonte') == 'API' for c in self.correcoes_sugeridas)
        dados_para_salvar = None

        if ha_correcoes_api:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Aplicar Correções de Endereço?")
            msg_box.setText("Foram encontradas sugestões de correção de endereço pela API.")
            msg_box.setInformativeText("Você deseja aplicar estas correções no arquivo final?")
            msg_box.setIcon(QMessageBox.Icon.Question)
            
            btn_salvar_tudo = msg_box.addButton("Sim, Aplicar Todas as Correções", QMessageBox.ButtonRole.YesRole)
            btn_salvar_formato = msg_box.addButton("Não, Manter Endereços Originais", QMessageBox.ButtonRole.NoRole)
            msg_box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
            
            msg_box.exec()
            
            clicked_button = msg_box.clickedButton()
            if clicked_button == btn_salvar_tudo:
                dados_para_salvar = self.dados_com_todas_correcoes
            elif clicked_button == btn_salvar_formato:
                dados_para_salvar = self.dados_apenas_formato
            else:
                self.status_label.setText("Operação de salvamento cancelada.")
                return
        else:
            reply = QMessageBox.question(self, 'Salvar Arquivo', 
                                         "Nenhuma correção de endereço foi sugerida pela API.\nDeseja salvar o arquivo com as correções de formato?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                         QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                dados_para_salvar = self.dados_com_todas_correcoes
            else:
                self.status_label.setText("Operação de salvamento cancelada.")
                return

        original_path = self.file_path_edit.text()
        base, ext = os.path.splitext(os.path.basename(original_path))
        default_filename = os.path.join(os.path.dirname(original_path), f"{base}_corrigido{ext}")
        caminho_saida, _ = QFileDialog.getSaveFileName(self, "Salvar Arquivo Corrigido", default_filename, "Arquivos CSV (*.csv)")
        
        if caminho_saida and dados_para_salvar:
            sucesso, mensagem = salvar_csv_processado(caminho_saida, dados_para_salvar)
            if sucesso:
                QMessageBox.information(self, "Sucesso", mensagem)
            else:
                QMessageBox.critical(self, "Erro ao Salvar", mensagem)
            self.status_label.setText(mensagem)

if __name__ == "__main__":
    setup_logging()
    logging.info("Aplicação iniciada.")
    app = QApplication(sys.argv)
    app.setStyleSheet("QWidget { font-size: 10pt; } QPushButton { padding: 8px; }")
    window = ValidadorCSVApp()
    window.show()
    sys.exit(app.exec())
